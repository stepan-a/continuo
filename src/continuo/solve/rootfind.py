"""Pluggable nonlinear solvers for the numerical steady state.

The steady state ``x_ss`` solves the *algebraic* system

    g(x) = F(0, x, e, θ) = 0,

the model with every time derivative set to zero. This is a nonlinear
root-find, and it is a different problem from the *linear* solve chosen by
``simulate(solver=…)`` (see :mod:`continuo.solve.linsolve`): there the
backend factorises the stacked Jacobian of one Newton step; here the
backend *is* the outer nonlinear iteration. The two ``solver=`` options
therefore name disjoint sets of methods.

Each backend implements the :class:`SteadySolver` protocol — a single
:meth:`~SteadySolver.solve` taking a :class:`RootProblem` (the residual
``g``, its analytic Jacobian ``jac``, the starting iterate ``x0`` and a
CasADi residual ``Function`` for the backends that consume one directly)
and returning a :class:`RootResult`. continuo builds an *exact* Jacobian by
CasADi automatic differentiation, so methods that exploit it (Newton, the
MINPACK ``hybr`` / ``lm`` families, KINSOL) are preferred over
Jacobian-free ones, which are offered for completeness.

Backends:

- :class:`NewtonSolver` — Newton with an Armijo backtracking line search.
  Exact Jacobian, quadratic local convergence; the fast path, selectable
  but not in the default ``auto`` chain.
- :class:`ScipyRootSolver` — wraps :func:`scipy.optimize.root`: ``hybr``
  (MINPACK Powell hybrid / trust-region dogleg), ``lm`` (Levenberg–
  Marquardt), and the Jacobian-free ``broyden`` / ``krylov`` / ``df-sane``
  / ``anderson`` families.
- :class:`KinsolSolver` — SUNDIALS KINSOL through CasADi's ``rootfinder``,
  a production Newton with a line-search globalisation. Offered only when
  CasADi was built with the plugin (:func:`available_steady_solvers`).
- :class:`HomotopySolver` — Newton homotopy
  ``H(x, λ) = g(x) − (1 − λ) g(x₀)`` marched from ``λ = 0`` (where ``x₀``
  is exact) to ``λ = 1`` (where ``H = g``), each step solved by an inner
  solver. The Jacobian of ``H`` in ``x`` is exactly ``jac``, so the
  analytic Jacobian is reused unchanged. The robustness tool for a poor
  initial guess.

``select_steady_solver(None)`` / ``"auto"`` returns an :class:`AutoSolver`
that tries ``hybr → lm → homotopy`` and keeps the first that converges —
the robust trust-region first, then a least-squares and a continuation
fallback for near-singular Jacobians and poor initial guesses.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import casadi as ca
import numpy as np

from continuo.solve.errors import SolveError

logger = logging.getLogger(__name__)

__all__ = [
    "SteadySolver",
    "RootProblem",
    "RootResult",
    "NewtonSolver",
    "ScipyRootSolver",
    "KinsolSolver",
    "HomotopySolver",
    "AutoSolver",
    "STEADY_SOLVERS",
    "available_steady_solvers",
    "select_steady_solver",
]


# ---------------------------------------------------------------------------
# problem / result / protocol
# ---------------------------------------------------------------------------


@dataclass
class RootProblem:
    """A square nonlinear system ``g(x) = 0`` with an analytic Jacobian.

    ``g`` and ``jac`` are NumPy callables (the residual and ``∂g/∂x`` at a
    point); ``x0`` is the starting iterate. ``residual_function`` is an
    optional CasADi ``Function`` mapping ``x`` to the residual with the
    exogenous and parameters already baked in — KINSOL consumes it directly
    rather than the NumPy callables. ``names`` labels the unknowns for
    diagnostics.
    """

    g: Callable[[np.ndarray], np.ndarray]
    jac: Callable[[np.ndarray], np.ndarray]
    x0: np.ndarray
    residual_function: ca.Function | None = None
    names: tuple[str, ...] = ()

    @property
    def n(self) -> int:
        return int(self.x0.size)

    def norm(self, x: np.ndarray) -> float:
        """The infinity norm of the residual, ``+inf`` if non-finite."""
        value = float(np.linalg.norm(self.g(x), np.inf))
        return value if np.isfinite(value) else np.inf


@dataclass
class RootResult:
    """The outcome of a nonlinear solve.

    ``success`` means the residual norm fell below the requested tolerance.
    ``algorithm`` records which backend produced ``x`` (for ``auto`` this is
    the member that won); ``message`` carries a human-readable note, used in
    the :class:`SolveError` raised when a solve fails.
    """

    x: np.ndarray
    success: bool
    iterations: int
    residual_norm: float
    algorithm: str
    message: str = ""


@runtime_checkable
class SteadySolver(Protocol):
    """A pluggable nonlinear solver for ``g(x) = 0``."""

    name: str

    def solve(self, problem: RootProblem, *, tol: float, max_iter: int) -> RootResult:
        """Solve ``problem``; return a :class:`RootResult` (never raises on non-convergence)."""
        ...


# ---------------------------------------------------------------------------
# Newton (default)
# ---------------------------------------------------------------------------

_LINE_SEARCH_STEPS = 30


_ARMIJO_C1 = 1e-4  # sufficient-decrease coefficient for the line search


class NewtonSolver:
    """Newton's method with an Armijo backtracking line search.

    Each step solves ``jac(x) Δ = −g(x)`` (dense; the steady system is small)
    and backtracks ``α = 1, ½, ¼, …`` until the step gives a *sufficient*
    decrease of the merit ``φ(x) = ½‖g(x)‖₂²`` — the Armijo condition
    ``φ(x + αΔ) ≤ (1 − 2 c₁ α) φ(x)`` (for a Newton direction the merit's
    directional derivative is ``∇φ·Δ = −‖g‖₂² = −2φ``). This is stricter than
    accepting any norm decrease: it rules out the crawling, near-zero steps a
    bare "did the norm drop?" test admits, while keeping quadratic
    convergence near the solution (``α = 1`` is taken there). The exact CasADi
    Jacobian supplies ``Δ``. A singular Jacobian, a non-finite residual, or a
    step that fails the Armijo test yields ``success=False`` rather than an
    exception, so :class:`AutoSolver` can fall through to another backend.

    ``line_search_steps`` caps the backtracking halvings per Newton step.
    """

    name = "newton"

    def __init__(self, *, line_search_steps: int = _LINE_SEARCH_STEPS):
        self.line_search_steps = line_search_steps

    def solve(self, problem: RootProblem, *, tol: float, max_iter: int) -> RootResult:
        x = np.array(problem.x0, dtype=float)
        for it in range(max_iter):
            g = problem.g(x)
            gnorm = float(np.linalg.norm(g, np.inf))
            if not np.isfinite(gnorm):
                return RootResult(x, False, it, np.inf, self.name, "non-finite residual")
            if gnorm < tol:
                return RootResult(x, True, it, gnorm, self.name)
            try:
                step = np.linalg.solve(problem.jac(x), -g)
            except np.linalg.LinAlgError:
                return RootResult(x, False, it, gnorm, self.name, "Jacobian is singular")
            x_next = _armijo_line_search(problem, x, g, step, self.line_search_steps)
            if x_next is None:
                return RootResult(x, False, it, gnorm, self.name, "line search found no descent")
            x = x_next
        final = problem.norm(x)
        return RootResult(
            x, final < tol, max_iter, final, self.name, f"did not converge in {max_iter} steps"
        )


def _armijo_line_search(
    problem: RootProblem, x: np.ndarray, g: np.ndarray, step: np.ndarray, steps: int
) -> np.ndarray | None:
    """Backtrack on ``α`` until Armijo sufficient decrease of ``½‖g‖₂²`` holds.

    ``g`` is the residual at ``x`` (already computed by the caller). For a
    Newton direction ``∇φ·Δ = −‖g‖₂²``, so the test ``φ(x+αΔ) ≤ φ(x) + c₁ α
    ∇φ·Δ`` becomes ``φ(x+αΔ) ≤ (1 − 2 c₁ α) φ(x)``. Returns the accepted
    iterate, or ``None`` if no ``α`` in ``steps`` halvings satisfies it.
    """
    phi0 = 0.5 * float(g @ g)
    alpha = 1.0
    for _ in range(steps):
        candidate = x + alpha * step
        gc = problem.g(candidate)
        phi = 0.5 * float(gc @ gc)
        if np.isfinite(phi) and phi <= (1.0 - 2.0 * _ARMIJO_C1 * alpha) * phi0:
            return candidate
        alpha *= 0.5
    return None


# ---------------------------------------------------------------------------
# SciPy (hybr / lm / broyden / krylov / df-sane / anderson)
# ---------------------------------------------------------------------------


class ScipyRootSolver:
    """A backend wrapping :func:`scipy.optimize.root`.

    ``method`` is the SciPy method name; ``uses_jac`` is whether it consumes
    the analytic Jacobian (the MINPACK ``hybr`` / ``lm`` families do; the
    quasi-Newton / Krylov / spectral families are Jacobian-free). ``name`` is
    the continuo preset under which the backend is exposed. ``scipy_options``
    is merged over continuo's tolerance-derived defaults and passed straight
    to :func:`scipy.optimize.root` as its ``options`` argument — e.g.
    ``{"factor": 0.1}`` for ``hybr``, ``{"jac_options": {"method": "gmres"}}``
    for ``krylov``, ``{"M": 5}`` for ``anderson``. The achieved residual norm
    is checked against ``tol`` independently of SciPy's own convergence flag,
    so the contract — ``‖g‖∞ < tol`` — is uniform across backends.
    Jacobian-free methods may need a looser ``tol`` to report success.
    """

    def __init__(
        self,
        method: str,
        *,
        uses_jac: bool,
        name: str | None = None,
        scipy_options: dict[str, Any] | None = None,
    ):
        self.method = method
        self.uses_jac = uses_jac
        self.name = name or method
        self.scipy_options = dict(scipy_options or {})

    def solve(self, problem: RootProblem, *, tol: float, max_iter: int) -> RootResult:
        from scipy.optimize import root

        kwargs: dict[str, Any] = {"method": self.method}
        if self.uses_jac:  # MINPACK hybr / lm consume the analytic Jacobian
            kwargs["jac"] = problem.jac
            options = {"xtol": min(tol, 1e-12)}
        elif self.method == "df-sane":  # spectral method: caps iterations via maxfev
            options = {"fatol": tol, "maxfev": max(max_iter, 1000)}
        else:  # broyden / krylov / anderson quasi-Newton family
            options = {"fatol": tol, "maxiter": max(max_iter, 1000)}
        options.update(self.scipy_options)  # user options win over the defaults
        kwargs["options"] = options
        try:
            sol = root(problem.g, problem.x0, **kwargs)
        except Exception as exc:  # SciPy raises on some non-convergence paths
            logger.debug("%s solve raised, treated as non-convergence", self.name, exc_info=exc)
            return RootResult(
                np.array(problem.x0, float), False, 0, problem.norm(problem.x0), self.name, str(exc)
            )
        x = np.asarray(sol.x, dtype=float).reshape(-1)
        norm = problem.norm(x)
        # Backend-defined iteration count: nit where SciPy reports it, else nfev —
        # not directly comparable to the Newton / homotopy iteration counts.
        iterations = int(sol.get("nit", sol.get("nfev", 0))) if hasattr(sol, "get") else 0
        success = norm < tol
        message = "" if success else f"{self.method}: ‖g‖∞={norm:.2e} ≥ tol ({sol.message})"
        return RootResult(x, success, iterations, norm, self.name, message)


# ---------------------------------------------------------------------------
# KINSOL (SUNDIALS, via CasADi)
# ---------------------------------------------------------------------------


_KINSOL_STRATEGIES = ("linesearch", "none", "picard", "fp")


class KinsolSolver:
    """SUNDIALS KINSOL through CasADi's ``rootfinder``.

    A production-grade Newton with a line-search globalisation, consuming the
    CasADi residual ``Function`` directly (so the Jacobian is formed by
    CasADi AD internally). Requires a CasADi built with the KINSOL plugin;
    :func:`available_steady_solvers` gates the preset on
    ``ca.has_rootfinder("kinsol")``.

    ``strategy`` selects KINSOL's globalisation: ``"linesearch"`` (the
    default, a line-search Newton), ``"none"`` (an undamped Newton),
    ``"picard"`` (Picard iteration) or ``"fp"`` (fixed-point iteration).
    """

    name = "kinsol"

    def __init__(self, *, strategy: str = "linesearch"):
        if strategy not in _KINSOL_STRATEGIES:
            raise SolveError(
                f"unknown kinsol strategy {strategy!r}; expected one of "
                f"{', '.join(_KINSOL_STRATEGIES)}"
            )
        self.strategy = strategy

    def solve(self, problem: RootProblem, *, tol: float, max_iter: int) -> RootResult:
        if problem.residual_function is None:
            return RootResult(
                np.array(problem.x0, float),
                False,
                0,
                problem.norm(problem.x0),
                self.name,
                "kinsol needs the CasADi residual function",
            )
        opts = {
            "abstol": tol,
            "max_iter": max_iter,
            "strategy": self.strategy,
            "print_level": 0,
        }
        try:
            rf = ca.rootfinder("steady_kinsol", "kinsol", problem.residual_function, opts)
            x = np.array(rf(problem.x0)).reshape(-1)
        except Exception as exc:  # KINSOL throws on failure to converge
            logger.debug("%s solve raised, treated as non-convergence", self.name, exc_info=exc)
            return RootResult(
                np.array(problem.x0, float), False, 0, problem.norm(problem.x0), self.name, str(exc)
            )
        norm = problem.norm(x)
        success = norm < tol
        message = "" if success else f"kinsol: ‖g‖∞={norm:.2e} ≥ tol"
        return RootResult(x, success, 0, norm, self.name, message)


# ---------------------------------------------------------------------------
# Homotopy / continuation (meta-solver)
# ---------------------------------------------------------------------------


@dataclass
class HomotopySolver:
    """Newton homotopy ``H(x, λ) = g(x) − (1 − λ) g(x₀)``.

    At ``λ = 0`` the starting iterate ``x₀`` is an exact root of ``H``; at
    ``λ = 1`` we have ``H = g``. The path is marched in ``steps`` increments,
    each solved by ``inner`` (Newton by default), warm-started from the
    previous point. Because the subtracted term is constant in ``x``, the
    Jacobian of ``H`` in ``x`` is exactly ``jac`` — the analytic Jacobian is
    reused unchanged. This rescues solves that diverge from a poor guess.
    """

    inner: SteadySolver = field(default_factory=lambda: NewtonSolver())
    steps: int = 12
    name: str = "homotopy"

    def solve(self, problem: RootProblem, *, tol: float, max_iter: int) -> RootResult:
        g0 = np.asarray(problem.g(problem.x0), dtype=float).reshape(-1)
        x = np.array(problem.x0, dtype=float)
        total_iters = 0
        for k in range(1, self.steps + 1):
            lam = k / self.steps
            offset = (1.0 - lam) * g0

            def g_lam(z: np.ndarray, offset: np.ndarray = offset) -> np.ndarray:
                return problem.g(z) - offset

            sub = RootProblem(g_lam, problem.jac, x, names=problem.names)
            res = self.inner.solve(sub, tol=tol, max_iter=max_iter)
            total_iters += res.iterations
            if not res.success:
                norm = problem.norm(x)
                return RootResult(
                    x,
                    False,
                    total_iters,
                    norm,
                    self.name,
                    f"homotopy stalled at λ={lam:.3g} ({res.message})",
                )
            x = res.x
        norm = problem.norm(x)
        return RootResult(x, norm < tol, total_iters, norm, self.name)


# ---------------------------------------------------------------------------
# auto (try a chain, first success wins)
# ---------------------------------------------------------------------------


@dataclass
class AutoSolver:
    """Try a sequence of backends, returning the first that converges.

    The default chain — ``hybr → lm → homotopy`` — leads with MINPACK's
    robust trust-region solve, falls back to Levenberg–Marquardt for a
    near-singular Jacobian, and finally to continuation for a poor initial
    guess. Each member only "wins" if it drives ``‖g‖∞`` below tolerance, so
    a later one runs only when the earlier ones fail. The winning backend is
    recorded in the :class:`RootResult` it returns.
    """

    chain: tuple[SteadySolver, ...]
    name: str = "auto"

    def solve(self, problem: RootProblem, *, tol: float, max_iter: int) -> RootResult:
        attempts: list[str] = []
        best = RootResult(np.array(problem.x0, float), False, 0, problem.norm(problem.x0), "auto")
        for solver in self.chain:
            res = solver.solve(problem, tol=tol, max_iter=max_iter)
            if res.success:
                return res
            attempts.append(f"{solver.name} (‖g‖∞={res.residual_norm:.2e})")
            if res.residual_norm < best.residual_norm:
                best = res
        return RootResult(
            best.x,
            False,
            best.iterations,
            best.residual_norm,
            "auto",
            "every backend failed: " + ", ".join(attempts),
        )


# ---------------------------------------------------------------------------
# registry and selection
# ---------------------------------------------------------------------------

# Preset name -> factory taking the backend's options as keyword arguments
# (see :func:`select_steady_solver`). ``newton``, ``homotopy`` and the SciPy
# presets are always available (SciPy is a hard dependency); ``kinsol`` is
# gated on the CasADi build (see :func:`available_steady_solvers`). For the
# SciPy presets the options are :func:`scipy.optimize.root` options; for the
# others they are the backend's constructor parameters.
STEADY_SOLVERS: dict[str, Callable[..., SteadySolver]] = {
    "newton": lambda **o: NewtonSolver(**o),
    "hybr": lambda **o: ScipyRootSolver("hybr", uses_jac=True, scipy_options=o),
    "lm": lambda **o: ScipyRootSolver("lm", uses_jac=True, scipy_options=o),
    "broyden": lambda **o: ScipyRootSolver(
        "broyden1", uses_jac=False, name="broyden", scipy_options=o
    ),
    "krylov": lambda **o: ScipyRootSolver("krylov", uses_jac=False, scipy_options=o),
    "df-sane": lambda **o: ScipyRootSolver("df-sane", uses_jac=False, scipy_options=o),
    "anderson": lambda **o: ScipyRootSolver("anderson", uses_jac=False, scipy_options=o),
    "kinsol": lambda **o: KinsolSolver(**o),
    "homotopy": lambda **o: HomotopySolver(**o),
}

# The order ``auto`` tries: MINPACK's robust trust-region hybrid, then
# Levenberg–Marquardt for a near-singular Jacobian, then continuation for a
# poor initial guess. (``newton`` stays a selectable preset for its fast
# quadratic path, but is not in the default chain.)
_AUTO_CHAIN = ("hybr", "lm", "homotopy")


def available_steady_solvers() -> frozenset[str]:
    """Preset names whose backend can run in this environment.

    SciPy is a hard dependency, so every backend but ``kinsol`` is always
    available; ``kinsol`` needs a CasADi built with the SUNDIALS plugin.
    """
    names = set(STEADY_SOLVERS) - {"kinsol"}
    if ca.has_rootfinder("kinsol"):
        names.add("kinsol")
    return frozenset(names)


def select_steady_solver(
    requested: str | SteadySolver | None,
    available: frozenset[str] | None = None,
    *,
    options: dict[str, Any] | None = None,
) -> SteadySolver:
    """Resolve a user request into a concrete :class:`SteadySolver`.

    ``requested`` is a preset name, an already-built solver instance (passed
    through for fine control), or ``None`` / ``"auto"`` to get the
    :class:`AutoSolver` chain. ``options`` configures a named preset — for
    the SciPy presets these are :func:`scipy.optimize.root` options, for the
    others the backend's parameters (e.g. ``{"strategy": "picard"}`` for
    ``kinsol``). Unknown or unavailable presets, options on an instance or on
    ``auto``, and invalid option keys all raise :class:`SolveError`.
    """
    if isinstance(requested, SteadySolver) and not isinstance(requested, str):
        if options:
            raise SolveError(
                "solver options cannot be combined with a constructed solver instance; "
                "set them on the instance instead"
            )
        return requested
    available = available_steady_solvers() if available is None else available
    name = requested or "auto"
    if name == "auto":
        if options:
            raise SolveError("solver options are not supported with 'auto'; name a solver")
        chain = tuple(STEADY_SOLVERS[n]() for n in _AUTO_CHAIN if n in available)
        return AutoSolver(chain)
    if name not in STEADY_SOLVERS:
        raise SolveError(f"unknown steady-state solver {name!r}; presets: {sorted(STEADY_SOLVERS)}")
    if name not in available:
        raise SolveError(
            f"steady-state solver {name!r} is unavailable here (available: {sorted(available)})"
        )
    try:
        return STEADY_SOLVERS[name](**(options or {}))
    except TypeError as exc:  # an unexpected option keyword for this backend
        raise SolveError(f"invalid options for steady-state solver {name!r}: {exc}") from exc

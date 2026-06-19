"""Perfect-foresight BVP driver: stacked collocation + Newton.

For one segment, the unknowns are every endogenous variable at every grid
point, stacked into the node block of ``X``. The residual ``G(X) = 0``
collects:

- the discretisation's collocation equations for the *dynamic* rows of
  ``F``, one block per interval (Crank–Nicolson, or a multi-stage
  collocation family — Gauss / Radau IIA / Lobatto IIIA — whose internal
  stage unknowns are appended to ``X`` after the node block);
- the *algebraic* rows of ``F`` enforced pointwise at every grid point;
- the boundary conditions — states pinned at ``t₀`` (from ``initval``),
  jumps pinned at ``t_N`` (the terminal steady state).

That is exactly square. ``G`` and its sparse Jacobian are built with CasADi;
Newton iterates with a SciPy sparse solve and a backtracking line search.

This module solves a single segment with a constant exogenous
configuration; the multi-segment driver (time-varying paths, stitching)
builds on it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import casadi as ca
import numpy as np
from scipy.sparse import csc_matrix

from continuo.codegen.residual import Residual, build_residual
from continuo.io.solution import Segment, Solution
from continuo.ir.model import Model
from continuo.parser.ast import (
    BinaryOp,
    DictEntry,
    DictLiteral,
    Expr,
    FunctionCall,
    Identifier,
    NumberLit,
    UnaryOp,
)
from continuo.solve.disc import (
    Grid,
    collocation_residual,
    crank_nicolson_residual,
    equidistribution_ratio,
    tableau_for,
    uniform_grid,
)
from continuo.solve.errors import SolveError
from continuo.solve.linsolve import LinearSolver, SuperluSolver, select_solver
from continuo.solve.numeric import constant_table, eval_constant
from continuo.solve.rootfind import SteadySolver, select_steady_solver
from continuo.solve.steady import evaluate_parameters, steady_state

__all__ = ["solve_pf", "solve_segment", "initial_conditions", "SolveStats"]

_TOL = 1e-10
_MAX_ITER = 50
_LINE_SEARCH_STEPS = 30
_RCOND_FLOOR = 1e-12  # reuse the cheap refactor until conditioning drops below this


@dataclass
class SolveStats:
    """Per-run linear-solver statistics, accumulated across Newton steps and segments.

    ``refactor_fallbacks`` counts the safety re-pivots — a reused factorisation
    that failed and was redone from scratch. ``min_rcond`` is the worst
    reciprocal-condition estimate seen (``None`` when the backend gives none),
    and ``fill`` is the latest ``nnz(L) + nnz(U)`` (``None`` when unavailable).
    """

    factorizations: int = 0
    refactorizations: int = 0
    refactor_fallbacks: int = 0
    min_rcond: float | None = None
    fill: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "factorizations": self.factorizations,
            "refactorizations": self.refactorizations,
            "refactor_fallbacks": self.refactor_fallbacks,
            "min_rcond": self.min_rcond,
            "fill": self.fill,
        }


def solve_pf(
    model: Model,
    *,
    horizon: float,
    intervals: int,
    exogenous: dict[str, float] | None = None,
    solver: str | LinearSolver | None = None,
    steady_solver: str | SteadySolver | None = None,
    steady_solver_options: dict[str, object] | None = None,
    scheme: str = "crank_nicolson",
    order: int | None = None,
    tol: float = _TOL,
    max_iter: int = _MAX_ITER,
) -> Solution:
    """Solve a model's perfect-foresight transition over ``[0, horizon]``.

    States start from ``initval``; jumps are anchored at the terminal
    steady state computed at ``exogenous`` (constant over the segment).

    ``solver`` selects the linear backend used for each Newton step: a
    preset name (``"superlu"``, ``"auto"``), a :class:`LinearSolver`
    instance, or ``None`` (the ``"auto"`` default). ``steady_solver``
    selects the nonlinear algorithm for the steady-state solves (preset
    name, :class:`SteadySolver` instance, or the ``"auto"`` default), and
    ``steady_solver_options`` configures a named preset. ``scheme`` /
    ``order`` choose the discretisation (default Crank–Nicolson; a
    collocation family with its order otherwise).
    """
    e = dict(exogenous or {})
    linear = select_solver(solver)
    steady_backend = select_steady_solver(steady_solver, options=steady_solver_options)
    theta = evaluate_parameters(model)
    residual = build_residual(model)
    grid = uniform_grid(horizon, intervals)

    ss = steady_state(model, exogenous=e, theta=theta, solver=steady_backend, nodomain=False)
    initial_states = initial_conditions(model, theta, e, ss, steady_solver=steady_backend)
    terminal_jumps = {name: ss[name] for name in model.jumps}
    guess = np.tile([ss[name] for name in model.endogenous], (grid.intervals + 1, 1))

    def constant_exogenous(_t: float) -> dict[str, float]:
        return e

    stats = SolveStats()
    path, iterations, _sym, _num = solve_segment(
        model,
        residual,
        grid,
        theta=theta,
        exogenous_at=constant_exogenous,
        initial_states=initial_states,
        terminal_jumps=terminal_jumps,
        guess=guess,
        solver=linear,
        scheme=scheme,
        order=order,
        stats=stats,
        tol=tol,
        max_iter=max_iter,
    )
    segment = Segment(
        start_time=0.0,
        times=grid.points,
        path=path,
        names=model.endogenous,
        info_set=e,
        terminal_ss=ss,
        iterations=iterations,
    )
    return Solution(
        segments=(segment,),
        names=model.endogenous,
        diagnostics={
            "scheme": scheme,
            "segments": 1,
            "newton_iterations": iterations,
            "solver": linear.name,
            "equidistribution_ratio": equidistribution_ratio(grid.points, path),
            **stats.as_dict(),
        },
    )


def solve_segment(
    model: Model,
    residual: Residual,
    grid: Grid,
    *,
    theta: dict[str, float],
    exogenous_at: Callable[[float], dict[str, float]],
    initial_states: dict[str, float],
    terminal_jumps: dict[str, float],
    guess: np.ndarray,
    solver: LinearSolver | None = None,
    scheme: str = "crank_nicolson",
    order: int | None = None,
    sym: Any = None,
    num: Any = None,
    stats: SolveStats | None = None,
    tol: float = _TOL,
    max_iter: int = _MAX_ITER,
) -> tuple[np.ndarray, int, Any, Any]:
    """Solve one segment, returning ``(path (N+1, n), iterations, sym, num)``.

    ``exogenous_at(t)`` gives the exogenous values at time ``t``; the
    collocation evaluates it at the interval collocation points and grid
    points, so a time-varying belief path is handled directly.

    ``scheme`` / ``order`` select the discretisation; a multi-stage
    collocation family carries internal stage unknowns in ``X`` (after the
    node block) which are seeded from the node ``guess`` and dropped from the
    returned path.

    ``solver`` is the pluggable linear backend used for each Newton step; it
    defaults to :class:`SuperluSolver`. The stacked Jacobian's pattern is
    constant over the segment — and, at a fixed grid (and scheme/order),
    across segments — so a caller solving a sequence of segments can pass the
    ``sym`` (symbolic analysis) and ``num`` (factorisation, to warm-start the
    pivots) returned here back in to skip re-analysing; when ``sym`` is
    ``None`` it is computed. ``stats`` accumulates linear-solver diagnostics
    in place across segments.
    """
    solver = solver or SuperluSolver()
    theta_dm = _vector(theta[name] for name in model.parameters)
    residual_fn, jacobian_fn = _build_system(
        model, residual, grid, theta_dm, exogenous_at, initial_states, terminal_jumps, scheme, order
    )
    x0 = _initial_vector(guess, grid, model, scheme, order)
    to_csc = _JacobianToCsc()
    if sym is None:
        sym = solver.analyze(to_csc(jacobian_fn(x0)))
    x, iterations, num = _newton(
        residual_fn, jacobian_fn, x0, tol, max_iter, solver, sym, num, stats, to_csc
    )
    # The leading node block is the solution path; trailing stage unknowns
    # (collocation schemes) are internal and dropped here.
    n = len(model.endogenous)
    path = x[: (grid.intervals + 1) * n].reshape(grid.intervals + 1, n)
    return path, iterations, sym, num


# ---------------------------------------------------------------------------
# stacked system
# ---------------------------------------------------------------------------


def _build_system(
    model: Model,
    residual: Residual,
    grid: Grid,
    theta: ca.DM,
    exogenous_at: Callable[[float], dict[str, float]],
    initial_states: dict[str, float],
    terminal_jumps: dict[str, float],
    scheme: str = "crank_nicolson",
    order: int | None = None,
) -> tuple[ca.Function, ca.Function]:
    n = len(model.endogenous)
    n_dynamic = len(model.states) + len(model.jumps)
    algebraic_residual = residual.algebraic_function
    index = {name: k for k, name in enumerate(model.endogenous)}
    points = grid.intervals + 1
    xdot_zero = ca.DM.zeros(n_dynamic, 1)

    def exogenous(t: float) -> ca.DM:
        values = exogenous_at(float(t))
        return _vector(values.get(name, 0.0) for name in model.exogenous)

    # The interval block, plus the unknown vector X. Crank–Nicolson keeps the
    # bare node vector; a collocation family appends per-interval stage
    # unknowns (n per stage: n_dynamic derivatives then n_algebraic values).
    if scheme == "crank_nicolson":
        interval = crank_nicolson_residual(residual)
        dynamic_rows = residual.dynamic_rows
        X = ca.SX.sym("X", n * points)
        interval_rows: list[ca.SX] = []
        midpoints = grid.midpoints
        steps = grid.steps
        for i in range(grid.intervals):
            t_mid = midpoints[i]
            midpoint = interval(
                _block(X, n, i), _block(X, n, i + 1), exogenous(t_mid), theta, t_mid, steps[i]
            )
            interval_rows.extend(midpoint[r] for r in dynamic_rows)
    else:
        tableau = tableau_for(scheme, order)
        interval = collocation_residual(residual, tableau)
        s = tableau.stages
        nodes = tableau.c
        n_algebraic = n - n_dynamic
        offset = n * points  # start of the stage block
        X = ca.SX.sym("X", offset + grid.intervals * s * n)
        steps = grid.steps
        interval_rows = []
        for i in range(grid.intervals):
            t_i = grid.points[i]
            step = steps[i]
            stages = [X[offset + (i * s + j) * n : offset + (i * s + j) * n + n] for j in range(s)]
            v = ca.vertcat(*(st[:n_dynamic] for st in stages))
            w = ca.vertcat(*(st[n_dynamic:] for st in stages)) if n_algebraic else ca.DM.zeros(0, 1)
            e = ca.vertcat(*(exogenous(t_i + nodes[j] * step) for j in range(s)))
            interval_rows.append(
                interval(_block(X, n, i), _block(X, n, i + 1), v, w, e, theta, t_i, step)
            )

    rows: list[ca.SX] = list(interval_rows)
    for j in range(points):
        t_j = grid.points[j]
        rows.append(algebraic_residual(xdot_zero, _block(X, n, j), exogenous(t_j), theta, t_j))
    for state in model.states:
        rows.append(_block(X, n, 0)[index[state]] - initial_states[state])
    for jump in model.jumps:
        rows.append(_block(X, n, points - 1)[index[jump]] - terminal_jumps[jump])

    g = ca.vertcat(*rows)
    residual_fn = ca.Function("G", [X], [g])
    jacobian_fn = ca.Function("J", [X], [ca.jacobian(g, X)])
    return residual_fn, jacobian_fn


def _block(x: ca.SX, n: int, j: int) -> ca.SX:
    """The ``j``-th node block (``n`` endogenous values) of the unknown vector."""
    return x[j * n : (j + 1) * n]


def _initial_vector(
    guess: np.ndarray, grid: Grid, model: Model, scheme: str, order: int | None
) -> np.ndarray:
    """The starting iterate: the flattened node guess, plus seeded stage unknowns."""
    node = guess.reshape(-1).astype(float)
    if scheme == "crank_nicolson":
        return node
    n_dynamic = len(model.states) + len(model.jumps)
    seed = _stage_seed(guess, grid, tableau_for(scheme, order), n_dynamic)
    return np.concatenate([node, seed])


def _stage_seed(guess: np.ndarray, grid: Grid, tableau, n_dynamic: int) -> np.ndarray:
    """Seed each interval's stage unknowns from the node guess.

    Stage derivatives take the secant slope across the interval; stage
    algebraic values are linearly interpolated between the interval ends —
    laid out interval-major, stage-major, derivatives then algebraic, to
    match the stage block of ``X``.
    """
    s = tableau.stages
    steps = grid.steps
    seeds: list[np.ndarray] = []
    for i in range(grid.intervals):
        x_i, x_next = guess[i], guess[i + 1]
        slope = (x_next[:n_dynamic] - x_i[:n_dynamic]) / steps[i]
        for j in range(s):
            c = tableau.c[j]
            seeds.append(slope)
            seeds.append((1.0 - c) * x_i[n_dynamic:] + c * x_next[n_dynamic:])
    return np.concatenate(seeds) if seeds else np.zeros(0)


# ---------------------------------------------------------------------------
# Newton
# ---------------------------------------------------------------------------


def _newton(
    residual_fn: ca.Function,
    jacobian_fn: ca.Function,
    x: np.ndarray,
    tol: float,
    max_iter: int,
    solver: LinearSolver,
    sym: Any,
    num: Any = None,
    stats: SolveStats | None = None,
    to_csc: _JacobianToCsc | None = None,
) -> tuple[np.ndarray, int, Any]:
    """Run Newton, returning ``(x, iterations, num)``.

    ``num`` may carry a factorisation from a previous segment (same sparsity
    pattern) to warm-start the pivots; the final factorisation is returned so
    the caller can carry it forward in turn. ``stats`` accumulates linear-solver
    diagnostics in place. ``to_csc`` reuses the constant Jacobian sparsity
    pattern across steps (a fresh builder is created when ``None``).
    """
    stats = stats if stats is not None else SolveStats()
    to_csc = to_csc if to_csc is not None else _JacobianToCsc()

    def residual(z: np.ndarray) -> np.ndarray:
        return np.array(residual_fn(z)).reshape(-1)

    g = residual(x)
    for iteration in range(1, max_iter + 1):
        current = np.linalg.norm(g, np.inf)
        if current < tol:
            return x, iteration - 1, num
        num = _refresh(solver, to_csc(jacobian_fn(x)), sym, num, stats)
        step = solver.solve(num, -g)
        if not np.all(np.isfinite(step)):
            raise SolveError("singular Jacobian in the perfect-foresight solve")
        # Carry the accepted line-search residual into the next iteration (its
        # norm is the convergence test), so the residual is evaluated once per
        # step instead of being recomputed at the top of the loop.
        x, g = _line_search(x, step, current, residual)
    raise SolveError(
        "perfect-foresight solve did not converge; refine the grid or supply a better initial_guess"
    )


def _refresh(solver: LinearSolver, a: csc_matrix, sym: Any, num: Any, stats: SolveStats) -> Any:
    """Refresh the numeric factorisation: a cheap refactor when safe, else a full factor.

    Reuses the pivot order (``refactor``) on a healthy factorisation, but falls
    back to a full ``factor`` for the first step, when conditioning degrades, or
    when a refactor with stale pivots fails (e.g. a KLU zero pivot). Records the
    work and the resulting conditioning / fill in ``stats``.
    """
    if num is None or _degraded(solver.rcond(num)):
        num = solver.factor(a, sym)
        stats.factorizations += 1
    else:
        try:
            num = solver.refactor(a, sym, num)
            stats.refactorizations += 1
        except SolveError:  # stale pivots: redo a full factorisation
            num = solver.factor(a, sym)
            stats.factorizations += 1
            stats.refactor_fallbacks += 1
    rcond = solver.rcond(num)
    if rcond is not None:
        stats.min_rcond = rcond if stats.min_rcond is None else min(stats.min_rcond, rcond)
    stats.fill = _fill(solver, num)
    return num


def _fill(solver: LinearSolver, num: Any) -> int | None:
    """The factorisation's ``nnz(L) + nnz(U)`` when the backend exposes it."""
    reporter = getattr(solver, "nnz", None)
    return reporter(num) if reporter is not None else None


def _degraded(rcond: float | None) -> bool:
    """Whether a reused factorisation is too ill-conditioned to keep refactoring."""
    return rcond is not None and rcond < _RCOND_FLOOR


def _line_search(
    x: np.ndarray, step: np.ndarray, base: float, residual: Callable[[np.ndarray], np.ndarray]
) -> tuple[np.ndarray, np.ndarray]:
    """Backtrack to a residual-decreasing step, returning ``(candidate, residual)``.

    Returns the accepted candidate together with its residual vector so the
    caller can reuse it as the next iterate's residual without re-evaluating.
    """
    alpha = 1.0
    for _ in range(_LINE_SEARCH_STEPS):
        candidate = x + alpha * step
        g = residual(candidate)
        if np.linalg.norm(g, np.inf) < base:
            return candidate, g
        alpha *= 0.5
    candidate = x + alpha * step
    return candidate, residual(candidate)


class _JacobianToCsc:
    """Build a CSC matrix from a CasADi Jacobian, caching the (constant) pattern.

    The Jacobian ``Function`` has a fixed sparsity pattern, so the compressed-
    column structure (``indptr`` / ``indices``) is captured from the first
    evaluation and reused; later calls only refill the numeric ``data``. This
    avoids re-extracting the triplet and rebuilding the matrix from scratch on
    every Newton iteration.
    """

    __slots__ = ("_indptr", "_indices", "_shape")

    def __init__(self) -> None:
        self._indptr: np.ndarray | None = None
        self._indices: np.ndarray = np.empty(0, dtype=np.int32)
        self._shape: tuple[int, int] = (0, 0)

    def __call__(self, jacobian: ca.DM) -> csc_matrix:
        if self._indptr is None:
            sp = jacobian.sparsity()
            self._indptr = np.asarray(sp.colind(), dtype=np.int32)
            self._indices = np.asarray(sp.row(), dtype=np.int32)
            self._shape = jacobian.shape
        data = np.asarray(jacobian.nonzeros(), dtype=float)
        return csc_matrix((data, self._indices, self._indptr), shape=self._shape)


# ---------------------------------------------------------------------------
# initial conditions
# ---------------------------------------------------------------------------


def initial_conditions(
    model: Model,
    theta: dict[str, float],
    e: dict[str, float],
    ss: dict[str, float],
    *,
    steady_solver: str | SteadySolver | None = None,
) -> dict[str, float]:
    """Evaluate the initval initial states.

    ``steady_state(v)`` resolves to ``ss`` — the initial steady state at the
    active exogenous ``e``. ``steady_state(v, e={…})`` resolves to the steady
    state at ``e`` overridden by the given exogenous values; this anchors the
    initial state at a *different* steady state than the active one, the case
    of a change already in effect at ``t = 0``. ``steady_solver`` selects the
    nonlinear algorithm for those override solves.
    """
    table = constant_table(theta, e, model)
    cache: dict[tuple[tuple[str, float], ...], dict[str, float]] = {}

    def steady_at(override: dict[str, float]) -> dict[str, float]:
        if not override:
            return ss
        merged = {**e, **override}
        key = tuple(sorted(merged.items()))
        if key not in cache:
            cache[key] = steady_state(
                model, exogenous=merged, theta=theta, solver=steady_solver, nodomain=False
            )
        return cache[key]

    result: dict[str, float] = {}
    for state in model.states:
        expr = model.initial_values.get(state)
        if expr is None:
            raise SolveError(f"state {state!r} has no initial value; add an initval block")
        resolved = _resolve_steady_state(expr, steady_at, table, model)
        result[state] = eval_constant(resolved, table, what=f"initial value of {state!r}")
    return result


def _resolve_steady_state(
    expr: Expr,
    steady_at: Callable[[dict[str, float]], dict[str, float]],
    table,
    model: Model,
) -> Expr:
    """Replace ``steady_state(v[, e={…}])`` calls with the numeric SS value of ``v``."""
    if isinstance(expr, FunctionCall):
        if expr.name.name == "steady_state" and expr.args and isinstance(expr.args[0], Identifier):
            override = _steady_override(expr, table, model)
            return NumberLit(steady_at(override)[expr.args[0].name])
        return FunctionCall(
            expr.name,
            [_resolve_steady_state(arg, steady_at, table, model) for arg in expr.args],
            list(expr.kwargs),
            expr.pos,
        )
    if isinstance(expr, BinaryOp):
        left = _resolve_steady_state(expr.left, steady_at, table, model)
        right = _resolve_steady_state(expr.right, steady_at, table, model)
        return BinaryOp(expr.op, left, right, expr.pos)
    if isinstance(expr, UnaryOp):
        operand = _resolve_steady_state(expr.operand, steady_at, table, model)
        return UnaryOp(expr.op, operand, expr.pos)
    if isinstance(expr, DictLiteral):
        return DictLiteral(
            [
                DictEntry(en.key, _resolve_steady_state(en.value, steady_at, table, model), en.pos)
                for en in expr.entries
            ],
            expr.pos,
        )
    return expr


def _steady_override(call: FunctionCall, table, model: Model) -> dict[str, float]:
    """The exogenous override from a ``steady_state(v, e={…})`` call (``{}`` if none)."""
    override: dict[str, float] = {}
    for kw in call.kwargs:
        if kw.name.name != "e":
            raise SolveError(
                f"steady_state(): unsupported argument {kw.name.name!r} "
                "(only e={…} is allowed here)"
            )
        if not isinstance(kw.value, DictLiteral):
            raise SolveError("steady_state() 'e' override must be a {…} mapping")
        for entry in kw.value.entries:
            name = entry.key.name
            if name not in model.exogenous:
                raise SolveError(f"steady_state() e={{…}}: {name!r} is not an exogenous variable")
            override[name] = eval_constant(
                entry.value, table, what=f"steady_state e override for {name!r}"
            )
    return override


def _vector(values) -> ca.DM:
    items = list(values)
    return ca.DM(items) if items else ca.DM.zeros(0, 1)

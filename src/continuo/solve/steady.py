"""Steady-state solver.

The steady state ``x_ss`` satisfies ``F(0, x_ss, e, θ, t) = 0`` — the model
with every time derivative set to zero, at a given exogenous configuration
``e`` and the parameter values ``θ``. Two paths:

- *analytical* — when the model carries a ``steady_state_model`` block, its
  assignments are a sequential closed form; evaluate them in order.
- *numerical* — otherwise, a nonlinear root-find on ``F(0, x, e, θ) = 0``
  using the codegen residual and its ``∂F/∂x``. The algorithm is pluggable
  (see :mod:`continuo.solve.rootfind`): ``solver=`` selects a preset
  (``"newton"``, ``"hybr"``, ``"kinsol"``, ``"homotopy"``, …) or an
  :class:`~continuo.solve.rootfind.SteadySolver` instance, defaulting to the
  ``"auto"`` chain (a trust-region hybrid, then least-squares, then
  continuation). The starting iterate comes from ``initial_guess`` (or a
  caller-supplied guess), falling back to 1.0 per variable.

Parameter values are themselves expressions (e.g. ``beta = 1/(1+rho)``);
:func:`evaluate_parameters` resolves them to numbers first, in declaration
order, so a value may reference an earlier parameter.
"""

from __future__ import annotations

import logging
from typing import Any

import casadi as ca
import numpy as np

from continuo.codegen.residual import build_residual
from continuo.codegen.translate import SymbolTable
from continuo.ir.model import Model
from continuo.solve.errors import SolveError
from continuo.solve.numeric import constant_table, eval_constant
from continuo.solve.rootfind import RootProblem, RootResult, SteadySolver, select_steady_solver
from continuo.solve.transform import (
    VarTransform,
    build_constrained_problem,
    build_transforms,
)

logger = logging.getLogger(__name__)

__all__ = ["evaluate_parameters", "steady_state", "directive_solver", "directive_solver_options"]


def _first_solver_query(model: Model):
    """The first ``steady`` directive that names a solver, or ``None``."""
    for query in model.steady_queries:
        if query.solver is not None:
            return query
    return None


def directive_solver(model: Model) -> str | None:
    """The nonlinear solver named on the model's ``steady`` directive, if any.

    Returns the first ``steady(solver=…)`` preset found, so a model file can
    set the steady-state algorithm once for both the standalone inspection
    and the internal solves of a run. ``None`` when no directive names one.
    """
    query = _first_solver_query(model)
    return query.solver if query is not None else None


def directive_solver_options(model: Model) -> dict[str, Any] | None:
    """The ``options={…}`` of the model's ``steady`` directive, if any.

    Read from the same directive :func:`directive_solver` takes the name from,
    so a name and its options stay together.
    """
    query = _first_solver_query(model)
    return query.options if query is not None else None


_TOL = 1e-10
_MAX_ITER = 50


def evaluate_parameters(model: Model) -> dict[str, float]:
    """Resolve the model's parameter-value expressions to numbers."""
    table = SymbolTable()
    values: dict[str, float] = {}
    for name, expr in model.parameter_values.items():
        values[name] = eval_constant(expr, table, what=f"value of parameter {name!r}")
        table.symbols[name] = ca.SX(values[name])
    missing = [p for p in model.parameters if p not in values]
    if missing:
        raise SolveError(f"parameter {missing[0]!r} has no value")
    return values


def steady_state(
    model: Model,
    *,
    exogenous: dict[str, float] | None = None,
    guess: dict[str, float] | None = None,
    solver: str | SteadySolver | None = None,
    options: dict[str, Any] | None = None,
    tol: float = _TOL,
    max_iter: int = _MAX_ITER,
) -> dict[str, float]:
    """Compute the steady state, returning ``{endogenous_name: value}``.

    ``exogenous`` gives the values of the ``varexo`` (default 0); ``guess``
    seeds / overrides the numerical starting iterate. ``solver`` selects the
    nonlinear algorithm for the numerical path — a preset name, a
    :class:`~continuo.solve.rootfind.SteadySolver` instance, or ``None`` (the
    ``"auto"`` default). ``options`` configures the named preset (e.g.
    ``{"strategy": "picard"}`` for ``kinsol``); both are ignored on the
    analytical path, which is a closed form.
    """
    theta = evaluate_parameters(model)
    e = dict(exogenous or {})
    if model.steady_state:
        return _analytical(model, theta, e)
    return _numerical(model, theta, e, guess, solver, options, tol, max_iter)


# ---------------------------------------------------------------------------
# analytical
# ---------------------------------------------------------------------------


def _analytical(model: Model, theta: dict[str, float], e: dict[str, float]) -> dict[str, float]:
    table = constant_table(theta, e, model)
    result: dict[str, float] = {}
    for name, expr in model.steady_state.items():
        result[name] = eval_constant(expr, table, what=f"steady state of {name!r}")
        table.symbols[name] = ca.SX(result[name])
    return result


# ---------------------------------------------------------------------------
# numerical
# ---------------------------------------------------------------------------


def _numerical(
    model: Model,
    theta: dict[str, float],
    e: dict[str, float],
    guess: dict[str, float] | None,
    solver: str | SteadySolver | None,
    options: dict[str, Any] | None,
    tol: float,
    max_iter: int,
) -> dict[str, float]:
    residual = build_residual(model)
    endogenous = model.endogenous
    theta_vec = _vector(theta[p] for p in model.parameters)
    e_vec = _vector(e.get(name, 0.0) for name in model.exogenous)
    xdot_zero = ca.DM.zeros(len(model.states) + len(model.jumps), 1)

    if model.constraints:
        # Reparametrise: solve in the unconstrained y, keeping x = T(y) strictly
        # inside its declared domain, then map the solution back to x.
        transforms = build_transforms(model, theta, e)
        y0 = _starting_iterate_y(model, theta, e, guess, transforms)
        problem, untransform = build_constrained_problem(
            residual, xdot_zero, e_vec, theta_vec, transforms, y0
        )
        result = _run(problem, solver, options, tol, max_iter)
        return dict(zip(endogenous, untransform(result.x).tolist(), strict=True))

    problem = _plain_problem(model, residual, xdot_zero, e_vec, theta_vec, theta, e, guess)
    result = _run(problem, solver, options, tol, max_iter)
    return dict(zip(endogenous, result.x.tolist(), strict=True))


def _plain_problem(
    model: Model,
    residual,
    xdot_zero: ca.DM,
    e_vec: ca.DM,
    theta_vec: ca.DM,
    theta: dict[str, float],
    e: dict[str, float],
    guess: dict[str, float] | None,
) -> RootProblem:
    """The unconstrained steady-state root problem, solved directly in ``x``."""
    endogenous = model.endogenous

    def g(x: np.ndarray) -> np.ndarray:
        out = residual.function(xdot_zero, ca.DM(x), e_vec, theta_vec, 0.0)
        return np.array(out).reshape(-1)

    def jac(x: np.ndarray) -> np.ndarray:
        out = residual.jacobian_x(xdot_zero, ca.DM(x), e_vec, theta_vec, 0.0)
        return np.array(out)

    return RootProblem(
        g,
        jac,
        _starting_iterate(model, theta, e, guess),
        residual_function=_residual_of_x(residual, xdot_zero, e_vec, theta_vec, len(endogenous)),
        names=tuple(endogenous),
    )


def _run(
    problem: RootProblem,
    solver: str | SteadySolver | None,
    options: dict[str, Any] | None,
    tol: float,
    max_iter: int,
) -> RootResult:
    """Select the backend, solve, and report — shared by both paths."""
    backend = select_steady_solver(solver, options=options)
    result = backend.solve(problem, tol=tol, max_iter=max_iter)
    if not result.success:
        raise SolveError(
            f"steady state did not converge ({result.message}); try another "
            "solver= or supply an initial_guess block closer to the solution"
        )
    logger.info(
        "steady state: %s converged in %d iterations (‖F‖∞=%.2e)",
        result.algorithm,
        result.iterations,
        result.residual_norm,
    )
    return result


def _residual_of_x(
    residual, xdot_zero: ca.DM, e_vec: ca.DM, theta_vec: ca.DM, n: int
) -> ca.Function:
    """A CasADi ``Function`` mapping ``x`` to ``F(0, x, e, θ, 0)`` for KINSOL."""
    x_sx = ca.SX.sym("x", n)
    f_sx = residual.function(xdot_zero, x_sx, e_vec, theta_vec, 0.0)
    return ca.Function("F_ss", [x_sx], [f_sx], ["x"], ["F"])


def _starting_iterate(
    model: Model, theta: dict[str, float], e: dict[str, float], guess: dict[str, float] | None
) -> np.ndarray:
    values: dict[str, float] = {}
    if model.initial_guess:
        table = constant_table(theta, e, model)
        for name, expr in model.initial_guess.items():
            values[name] = eval_constant(expr, table, what=f"initial_guess for {name!r}")
    if guess:
        values.update(guess)
    return np.array([values.get(name, 1.0) for name in model.endogenous], dtype=float)


def _starting_iterate_y(
    model: Model,
    theta: dict[str, float],
    e: dict[str, float],
    guess: dict[str, float] | None,
    transforms: list[VarTransform],
) -> np.ndarray:
    """Starting iterate in ``y``-space, aligned with ``transforms``.

    An explicit guess (from ``initial_guess`` or the caller) is mapped
    through ``T⁻¹`` — which validates it is strictly interior. Otherwise a
    constrained variable starts at ``y = 0`` (the interior point ``T(0)``)
    and an unconstrained one at ``1.0``, matching the plain path's default.
    """
    values: dict[str, float] = {}
    if model.initial_guess:
        table = constant_table(theta, e, model)
        for name, expr in model.initial_guess.items():
            values[name] = eval_constant(expr, table, what=f"initial_guess for {name!r}")
    if guess:
        values.update(guess)
    y0 = np.empty(len(transforms), dtype=float)
    for i, transform in enumerate(transforms):
        if transform.name in values:
            y0[i] = transform.inverse(values[transform.name])
        elif transform.constrained:
            y0[i] = 0.0
        else:
            y0[i] = 1.0
    return y0


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _vector(values) -> ca.DM:
    items = list(values)
    return ca.DM(items) if items else ca.DM.zeros(0, 1)

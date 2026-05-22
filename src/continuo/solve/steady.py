"""Steady-state solver.

The steady state ``x_ss`` satisfies ``F(0, x_ss, e, θ, t) = 0`` — the model
with every time derivative set to zero, at a given exogenous configuration
``e`` and the parameter values ``θ``. Two paths:

- *analytical* — when the model carries a ``steady_state_model`` block, its
  assignments are a sequential closed form; evaluate them in order.
- *numerical* — otherwise, Newton's method on ``F(0, x, e, θ) = 0`` using
  the codegen residual and its ``∂F/∂x``, with a backtracking line search
  for robustness. The starting iterate comes from ``initial_guess`` (or a
  caller-supplied guess), falling back to 1.0 per variable.

Parameter values are themselves expressions (e.g. ``beta = 1/(1+rho)``);
:func:`evaluate_parameters` resolves them to numbers first, in declaration
order, so a value may reference an earlier parameter.
"""

from __future__ import annotations

import casadi as ca
import numpy as np

from continuo.codegen.residual import build_residual
from continuo.codegen.translate import SymbolTable
from continuo.ir.model import Model
from continuo.solve.errors import SolveError
from continuo.solve.numeric import constant_table, eval_constant

__all__ = ["evaluate_parameters", "steady_state"]

_TOL = 1e-10
_MAX_ITER = 50
_LINE_SEARCH_STEPS = 30


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
    tol: float = _TOL,
    max_iter: int = _MAX_ITER,
) -> dict[str, float]:
    """Compute the steady state, returning ``{endogenous_name: value}``.

    ``exogenous`` gives the values of the ``varexo`` (default 0); ``guess``
    seeds / overrides the numerical starting iterate.
    """
    theta = evaluate_parameters(model)
    e = dict(exogenous or {})
    if model.steady_state:
        return _analytical(model, theta, e)
    return _numerical(model, theta, e, guess, tol, max_iter)


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
    tol: float,
    max_iter: int,
) -> dict[str, float]:
    residual = build_residual(model)
    endogenous = model.endogenous
    theta_vec = _vector(theta[p] for p in model.parameters)
    e_vec = _vector(e.get(name, 0.0) for name in model.exogenous)
    xdot_zero = ca.DM.zeros(len(model.states) + len(model.jumps), 1)

    def g(x: np.ndarray) -> np.ndarray:
        out = residual.function(xdot_zero, ca.DM(x), e_vec, theta_vec, 0.0)
        return np.array(out).reshape(-1)

    def jac(x: np.ndarray) -> np.ndarray:
        out = residual.jacobian_x(xdot_zero, ca.DM(x), e_vec, theta_vec, 0.0)
        return np.array(out)

    def norm(x: np.ndarray) -> float:
        value = np.linalg.norm(g(x), np.inf)
        return value if np.isfinite(value) else np.inf

    x = _starting_iterate(model, theta, e, guess)
    for _ in range(max_iter):
        current = norm(x)
        if current < tol:
            return dict(zip(endogenous, x.tolist(), strict=True))
        try:
            step = np.linalg.solve(jac(x), -g(x))
        except np.linalg.LinAlgError:
            raise SolveError("steady-state Jacobian is singular") from None
        x = _line_search(x, step, current, norm)
    raise SolveError(
        "steady state did not converge; supply an initial_guess block with a "
        "starting iterate closer to the solution"
    )


def _line_search(x: np.ndarray, step: np.ndarray, base: float, norm) -> np.ndarray:
    alpha = 1.0
    for _ in range(_LINE_SEARCH_STEPS):
        candidate = x + alpha * step
        if norm(candidate) < base:
            return candidate
        alpha *= 0.5
    return x + alpha * step  # take the smallest step rather than stall


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


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _vector(values) -> ca.DM:
    items = list(values)
    return ca.DM(items) if items else ca.DM.zeros(0, 1)

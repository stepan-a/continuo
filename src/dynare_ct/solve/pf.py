"""Perfect-foresight BVP driver: stacked collocation + Newton.

For one segment, the unknowns are every endogenous variable at every grid
point, stacked into ``X ∈ ℝ^{n·(N+1)}``. The residual ``G(X) = 0`` collects:

- the Crank–Nicolson collocation equations for the *dynamic* rows of ``F``,
  one block per interval;
- the *algebraic* rows of ``F`` enforced pointwise at every grid point;
- the boundary conditions — states pinned at ``t₀`` (from ``initval``),
  jumps pinned at ``t_N`` (the terminal steady state).

That is exactly square (``n·(N+1)`` equations and unknowns). ``G`` and its
sparse Jacobian are built with CasADi; Newton iterates with a SciPy sparse
solve and a backtracking line search.

This module solves a single segment with a constant exogenous
configuration; the multi-segment driver (time-varying paths, stitching)
builds on it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import casadi as ca
import numpy as np
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import spsolve

from dynare_ct.codegen.residual import Residual, build_residual
from dynare_ct.ir.model import Model
from dynare_ct.parser.ast import (
    BinaryOp,
    DictEntry,
    DictLiteral,
    Expr,
    FunctionCall,
    Identifier,
    NumberLit,
    UnaryOp,
)
from dynare_ct.solve.disc import Grid, crank_nicolson_residual, uniform_grid
from dynare_ct.solve.errors import SolveError
from dynare_ct.solve.numeric import constant_table, eval_constant
from dynare_ct.solve.steady import evaluate_parameters, steady_state

__all__ = ["PFSolution", "solve_pf", "solve_segment", "initial_conditions"]

_TOL = 1e-10
_MAX_ITER = 50
_LINE_SEARCH_STEPS = 30


@dataclass
class PFSolution:
    """A solved perfect-foresight path.

    ``path`` is shape ``(N+1, n)``; column ``k`` is the variable
    ``names[k]`` at each grid time in ``times``.
    """

    times: np.ndarray
    path: np.ndarray
    names: tuple[str, ...]
    iterations: int

    def series(self, name: str) -> np.ndarray:
        """The path of one variable over the grid."""
        return self.path[:, self.names.index(name)]

    def terminal(self) -> dict[str, float]:
        """The endogenous values at the final grid point."""
        return dict(zip(self.names, self.path[-1].tolist(), strict=True))


def solve_pf(
    model: Model,
    *,
    horizon: float,
    intervals: int,
    exogenous: dict[str, float] | None = None,
    tol: float = _TOL,
    max_iter: int = _MAX_ITER,
) -> PFSolution:
    """Solve a model's perfect-foresight transition over ``[0, horizon]``.

    States start from ``initval``; jumps are anchored at the terminal
    steady state computed at ``exogenous`` (constant over the segment).
    """
    e = dict(exogenous or {})
    theta = evaluate_parameters(model)
    residual = build_residual(model)
    grid = uniform_grid(horizon, intervals)

    ss = steady_state(model, exogenous=e)
    initial_states = initial_conditions(model, theta, e, ss)
    terminal_jumps = {name: ss[name] for name in model.jumps}
    guess = np.tile([ss[name] for name in model.endogenous], (grid.intervals + 1, 1))

    def constant_exogenous(_t: float) -> dict[str, float]:
        return e

    path, iterations = solve_segment(
        model,
        residual,
        grid,
        theta=theta,
        exogenous_at=constant_exogenous,
        initial_states=initial_states,
        terminal_jumps=terminal_jumps,
        guess=guess,
        tol=tol,
        max_iter=max_iter,
    )
    return PFSolution(grid.points, path, model.endogenous, iterations)


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
    tol: float = _TOL,
    max_iter: int = _MAX_ITER,
) -> tuple[np.ndarray, int]:
    """Solve one segment numerically, returning ``(path (N+1, n), iterations)``.

    ``exogenous_at(t)`` gives the exogenous values at time ``t``; the
    collocation evaluates it at the interval midpoints and grid points,
    so a time-varying belief path is handled directly.
    """
    theta_dm = _vector(theta[name] for name in model.parameters)
    residual_fn, jacobian_fn = _build_system(
        model, residual, grid, theta_dm, exogenous_at, initial_states, terminal_jumps
    )
    x0 = guess.reshape(-1).astype(float)
    x, iterations = _newton(residual_fn, jacobian_fn, x0, tol, max_iter)
    return x.reshape(grid.intervals + 1, len(model.endogenous)), iterations


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
) -> tuple[ca.Function, ca.Function]:
    n = len(model.endogenous)
    n_dynamic = len(model.states) + len(model.jumps)
    interval = crank_nicolson_residual(residual)
    full = residual.function
    dynamic_rows, algebraic_rows = _row_split(residual, model)
    index = {name: k for k, name in enumerate(model.endogenous)}

    def exogenous(t: float) -> ca.DM:
        values = exogenous_at(float(t))
        return _vector(values.get(name, 0.0) for name in model.exogenous)

    points = grid.intervals + 1
    X = ca.SX.sym("X", n * points)

    def block(j: int) -> ca.SX:
        return X[j * n : (j + 1) * n]

    rows: list[ca.SX] = []
    xdot_zero = ca.DM.zeros(n_dynamic, 1)
    for i in range(grid.intervals):
        t_mid = grid.midpoints[i]
        midpoint = interval(block(i), block(i + 1), exogenous(t_mid), theta, t_mid, grid.dt)
        rows.extend(midpoint[r] for r in dynamic_rows)
    for j in range(points):
        t_j = grid.points[j]
        pointwise = full(xdot_zero, block(j), exogenous(t_j), theta, t_j)
        rows.extend(pointwise[r] for r in algebraic_rows)
    for state in model.states:
        rows.append(block(0)[index[state]] - initial_states[state])
    for jump in model.jumps:
        rows.append(block(points - 1)[index[jump]] - terminal_jumps[jump])

    g = ca.vertcat(*rows)
    residual_fn = ca.Function("G", [X], [g])
    jacobian_fn = ca.Function("J", [X], [ca.jacobian(g, X)])
    return residual_fn, jacobian_fn


def _row_split(residual: Residual, model: Model) -> tuple[list[int], list[int]]:
    """Indices of the dynamic (depend on ẋ) and algebraic rows of F."""
    n = residual.expression.shape[0]
    dynamic_symbols = [residual.symbols.derivatives[name] for name in (*model.states, *model.jumps)]
    if not dynamic_symbols:  # a purely algebraic model has no ẋ
        return [], list(range(n))
    # tr=True orients the result per equation (row) rather than per variable.
    depends = ca.which_depends(residual.expression, ca.vertcat(*dynamic_symbols), 1, True)
    dynamic = [r for r, d in enumerate(depends) if d]
    algebraic = [r for r, d in enumerate(depends) if not d]
    return dynamic, algebraic


# ---------------------------------------------------------------------------
# Newton
# ---------------------------------------------------------------------------


def _newton(
    residual_fn: ca.Function, jacobian_fn: ca.Function, x: np.ndarray, tol: float, max_iter: int
) -> tuple[np.ndarray, int]:
    def norm(z: np.ndarray) -> float:
        value = np.linalg.norm(np.array(residual_fn(z)).reshape(-1), np.inf)
        return value if np.isfinite(value) else np.inf

    for iteration in range(1, max_iter + 1):
        g = np.array(residual_fn(x)).reshape(-1)
        current = np.linalg.norm(g, np.inf)
        if current < tol:
            return x, iteration - 1
        step = spsolve(_to_csc(jacobian_fn(x)), -g)
        if not np.all(np.isfinite(step)):
            raise SolveError("singular Jacobian in the perfect-foresight solve")
        x = _line_search(x, step, current, norm)
    raise SolveError(
        "perfect-foresight solve did not converge; refine the grid or supply a better initial_guess"
    )


def _line_search(x: np.ndarray, step: np.ndarray, base: float, norm) -> np.ndarray:
    alpha = 1.0
    for _ in range(_LINE_SEARCH_STEPS):
        candidate = x + alpha * step
        if norm(candidate) < base:
            return candidate
        alpha *= 0.5
    return x + alpha * step


def _to_csc(jacobian: ca.DM) -> csc_matrix:
    rows, cols = jacobian.sparsity().get_triplet()
    return csc_matrix((np.array(jacobian.nonzeros()), (rows, cols)), shape=jacobian.shape)


# ---------------------------------------------------------------------------
# initial conditions
# ---------------------------------------------------------------------------


def initial_conditions(
    model: Model, theta: dict[str, float], e: dict[str, float], ss: dict[str, float]
) -> dict[str, float]:
    """Evaluate the initval initial states, resolving steady_state(.) via ``ss``."""
    table = constant_table(theta, e, model)
    result: dict[str, float] = {}
    for state in model.states:
        expr = model.initial_values.get(state)
        if expr is None:
            raise SolveError(f"state {state!r} has no initial value; add an initval block")
        resolved = _resolve_steady_state(expr, ss)
        result[state] = eval_constant(resolved, table, what=f"initial value of {state!r}")
    return result


def _resolve_steady_state(expr: Expr, ss: dict[str, float]) -> Expr:
    """Replace ``steady_state(v)`` calls with the numeric SS value of ``v``."""
    if isinstance(expr, FunctionCall):
        if expr.name.name == "steady_state" and expr.args and isinstance(expr.args[0], Identifier):
            return NumberLit(ss[expr.args[0].name])
        return FunctionCall(
            expr.name,
            [_resolve_steady_state(arg, ss) for arg in expr.args],
            list(expr.kwargs),
            expr.pos,
        )
    if isinstance(expr, BinaryOp):
        left = _resolve_steady_state(expr.left, ss)
        right = _resolve_steady_state(expr.right, ss)
        return BinaryOp(expr.op, left, right, expr.pos)
    if isinstance(expr, UnaryOp):
        return UnaryOp(expr.op, _resolve_steady_state(expr.operand, ss), expr.pos)
    if isinstance(expr, DictLiteral):
        return DictLiteral(
            [DictEntry(e.key, _resolve_steady_state(e.value, ss), e.pos) for e in expr.entries],
            expr.pos,
        )
    return expr


def _vector(values) -> ca.DM:
    items = list(values)
    return ca.DM(items) if items else ca.DM.zeros(0, 1)

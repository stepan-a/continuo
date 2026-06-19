"""Adaptive mesh refinement for one perfect-foresight segment.

Given a segment (its boundary conditions and active beliefs), solve on a
sequence of meshes, **equidistributing** the solution curvature: at each pass
the intervals where the curvature indicator is above average are bisected,
and the segment is re-solved, until a global error estimate falls below the
requested tolerance (or a node cap / pass cap is hit). The reveal / terminal
node (``mark``) is preserved through refinement because we only ever *add*
nodes.

Two error estimators (the ``monitor=`` choice) decide convergence:

- ``residual`` (default) — the ODE defect of a smooth interpolant; no extra
  solve, and robust at a kink (no order assumption).
- ``richardson`` — a calibrated error magnitude from a solve on the
  once-bisected mesh, scaled by the scheme order. Costs one extra solve per
  pass and assumes the nominal order (so it under-refines at a kink).

Placement (where to refine) always uses the cheap curvature indicator.
"""

from __future__ import annotations

import casadi as ca
import numpy as np

from continuo.codegen.residual import Residual
from continuo.ir.model import Model
from continuo.solve.disc import (
    Grid,
    MonitorInput,
    aligned_grid,
    default_order,
    mesh_from_points,
    select_monitor,
)
from continuo.solve.pf import SolveStats, solve_segment

__all__ = ["refine_segment", "ADAPT_MONITORS"]

# Monitors that yield a global error magnitude (a tolerance test). curvature is
# placement-only, so it cannot drive the adaptive stop.
ADAPT_MONITORS = ("richardson", "residual")

_MAX_PASSES = 10
_CAP_FACTOR = 12  # node cap = _CAP_FACTOR * the initial interval count


def refine_segment(
    *,
    model: Model,
    residual: Residual,
    theta: dict[str, float],
    exogenous_at,
    initial_states: dict[str, float],
    terminal_jumps: dict[str, float],
    terminal_row: np.ndarray,
    scheme: str,
    order: int | None,
    solver,
    stats: SolveStats,
    start: float,
    horizon: float,
    intervals: int,
    mark: float,
    tol: float,
    monitor: str,
    cap: int | None = None,
    max_passes: int = _MAX_PASSES,
) -> tuple[Grid, int, np.ndarray, int]:
    """Solve one segment with adaptive refinement; return (grid, mark index, path, iterations)."""
    cap = cap if cap is not None else _CAP_FACTOR * intervals
    order_p = _scheme_order(scheme, order)
    n_dynamic = len(model.states) + len(model.jumps)
    stop = select_monitor(monitor)
    placement = select_monitor("curvature")
    dynamic_residual = (
        _dynamic_residual(model, residual, theta, exogenous_at) if monitor == "residual" else None
    )

    grid, _ = aligned_grid(start, horizon, intervals, mark)
    prev_points: np.ndarray | None = None
    prev_path: np.ndarray | None = None
    path = np.empty((0, 0))
    total_iterations = 0

    for current_pass in range(max_passes):
        guess = _guess(grid.points, prev_points, prev_path, terminal_row)
        path, iterations = _solve(
            model,
            residual,
            grid,
            theta,
            exogenous_at,
            initial_states,
            terminal_jumps,
            guess,
            solver,
            scheme,
            order,
            stats,
        )
        total_iterations += iterations

        if monitor == "richardson":
            fine = mesh_from_points(_bisect(grid.points))
            fine_guess = _guess(fine.points, grid.points, path, terminal_row)
            fine_path, fine_iterations = _solve(
                model,
                residual,
                fine,
                theta,
                exogenous_at,
                initial_states,
                terminal_jumps,
                fine_guess,
                solver,
                scheme,
                order,
                stats,
            )
            total_iterations += fine_iterations
            error = stop.assess(
                MonitorInput(grid=grid, path=path, order=order_p, refined=(fine, fine_path))
            )
        else:
            error = stop.assess(
                MonitorInput(
                    grid=grid, path=path, dynamic_residual=dynamic_residual, n_dynamic=n_dynamic
                )
            )

        converged = error.estimate is not None and error.estimate <= tol
        if converged or grid.intervals >= cap or current_pass == max_passes - 1:
            break

        weights = placement.assess(MonitorInput(grid=grid, path=path)).per_interval
        prev_points, prev_path = grid.points, path
        grid = mesh_from_points(_refine(grid.points, weights, cap - grid.intervals))

    mark_index = int(np.searchsorted(grid.points, mark))
    return grid, mark_index, path, total_iterations


def _solve(
    model,
    residual,
    grid,
    theta,
    exogenous_at,
    initial_states,
    terminal_jumps,
    guess,
    solver,
    scheme,
    order,
    stats,
) -> tuple[np.ndarray, int]:
    # A fresh symbolic analysis each mesh (the sparsity pattern changes with N).
    path, iterations, _sym, _num = solve_segment(
        model,
        residual,
        grid,
        theta=theta,
        exogenous_at=exogenous_at,
        initial_states=initial_states,
        terminal_jumps=terminal_jumps,
        guess=guess,
        solver=solver,
        scheme=scheme,
        order=order,
        stats=stats,
    )
    return path, iterations


def _scheme_order(scheme: str, order: int | None) -> int:
    if scheme == "crank_nicolson":
        return 2
    return order if order is not None else default_order(scheme)


def _bisect(points: np.ndarray) -> np.ndarray:
    """Every interval split in two (the coarse nodes are the even fine nodes)."""
    mids = 0.5 * (points[:-1] + points[1:])
    return np.sort(np.concatenate([points, mids]))


def _refine(points: np.ndarray, weights: np.ndarray, max_add: int) -> np.ndarray:
    """Bisect the above-average-curvature intervals (equidistribution).

    At most ``max_add`` intervals are bisected (the worst ones), so the node
    count stays within the cap.
    """
    mids = 0.5 * (points[:-1] + points[1:])
    chosen = np.flatnonzero(weights > weights.mean())
    if chosen.size == 0:  # all equal — still make progress on the worst interval
        chosen = np.array([int(np.argmax(weights))])
    if max_add > 0 and chosen.size > max_add:
        chosen = chosen[np.argsort(weights[chosen])[-max_add:]]
    return np.sort(np.concatenate([points, mids[chosen]]))


def _guess(
    new_points: np.ndarray,
    src_points: np.ndarray | None,
    src_path: np.ndarray | None,
    terminal_row: np.ndarray,
) -> np.ndarray:
    """Seed a solve on ``new_points`` from the previous solution, else the terminal SS."""
    if src_points is None or src_path is None:
        return np.tile(terminal_row, (len(new_points), 1))
    return np.column_stack(
        [np.interp(new_points, src_points, src_path[:, k]) for k in range(src_path.shape[1])]
    )


def _dynamic_residual(model: Model, residual: Residual, theta: dict[str, float], exogenous_at):
    """Build ``(t, x_full, xdot_dynamic) -> dynamic residual`` for the residual monitor."""
    theta_dm = (
        ca.DM([theta[p] for p in model.parameters]) if model.parameters else ca.DM.zeros(0, 1)
    )
    exogenous = model.exogenous

    def f(t: float, x_full: np.ndarray, xdot_dynamic: np.ndarray) -> np.ndarray:
        values = exogenous_at(float(t))
        e_vec = (
            ca.DM([values.get(name, 0.0) for name in exogenous]) if exogenous else ca.DM.zeros(0, 1)
        )
        out = residual.dynamic_function(ca.DM(xdot_dynamic), ca.DM(x_full), e_vec, theta_dm, t)
        return np.array(out).reshape(-1)

    return f

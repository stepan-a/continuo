"""Tests for the grid-error monitors (curvature / richardson / residual).

These exercise the monitor abstraction directly and check that the cheap
curvature diagnostic is surfaced in a Solution's diagnostics. No refinement
loop yet — that is a later step.
"""

from __future__ import annotations

import casadi as ca
import numpy as np
import pytest

from continuo.codegen.residual import build_residual
from continuo.ir import build
from continuo.parser import parse
from continuo.solve import SolveError, solve_pf
from continuo.solve.disc import (
    GridError,
    MonitorInput,
    equidistribution_ratio,
    select_monitor,
    uniform_grid,
)
from continuo.solve.pf import _row_split
from continuo.solve.steady import evaluate_parameters

# A linear scalar ODE with the analytic solution K(t) = exp(lam*t).
_LAM = -0.7
DECAY = f"""
var(state) K;
parameters lam;
lam = {_LAM};
model;
  diff(K) = lam * K;
end;
initval;
  K = 1.0;
end;
"""


def _model(src: str):
    return build(parse(src))


# --- registry -------------------------------------------------------------


def test_select_monitor_returns_named_preset():
    assert select_monitor("curvature").name == "curvature"
    assert select_monitor("richardson").name == "richardson"
    assert select_monitor("residual").name == "residual"


def test_unknown_monitor_rejected():
    with pytest.raises(SolveError, match="unknown error monitor"):
        select_monitor("magic")


def test_monitor_requires_its_inputs():
    grid = uniform_grid(1.0, 4)
    path = np.zeros((5, 1))
    with pytest.raises(SolveError, match="refined solution"):
        select_monitor("richardson").assess(MonitorInput(grid=grid, path=path))
    with pytest.raises(SolveError, match="dynamic-residual"):
        select_monitor("residual").assess(MonitorInput(grid=grid, path=path))


# --- curvature ------------------------------------------------------------


def test_curvature_flat_path_is_well_equidistributed():
    grid = uniform_grid(1.0, 10)
    line = np.linspace(0.0, 1.0, 11).reshape(-1, 1)  # straight line: zero curvature
    err = select_monitor("curvature").assess(MonitorInput(grid=grid, path=line))
    assert err.estimate is None
    assert err.equidistribution_ratio == pytest.approx(1.0, abs=1e-6)


def test_curvature_flags_a_localised_bend():
    grid = uniform_grid(1.0, 40)
    t = grid.points
    path = np.exp(-50.0 * t).reshape(-1, 1)  # sharp bend near t=0
    err = select_monitor("curvature").assess(MonitorInput(grid=grid, path=path))
    assert err.per_interval.shape == (40,)
    assert err.equidistribution_ratio > 5.0  # resolution badly misallocated on a uniform grid
    assert np.argmax(err.per_interval) < 5  # the bend is at the start


# --- richardson -----------------------------------------------------------


def test_richardson_estimate_tracks_true_error():
    # Crank-Nicolson (order 2): the Richardson estimate from N and 2N should be
    # close to the true max error of the coarse solve against exp(lam*t).
    m = _model(DECAY)
    coarse = solve_pf(m, horizon=2.0, intervals=20)
    fine = solve_pf(m, horizon=2.0, intervals=40)
    grid = uniform_grid(2.0, 20)
    est = (
        select_monitor("richardson")
        .assess(
            MonitorInput(
                grid=grid,
                path=coarse.path,
                order=2,
                refined=(uniform_grid(2.0, 40), fine.path),
            )
        )
        .estimate
    )
    true_error = float(np.max(np.abs(coarse["K"] - np.exp(_LAM * coarse.t))))
    assert est == pytest.approx(true_error, rel=0.3)


# --- residual -------------------------------------------------------------


def _dynamic_residual(model, residual, theta):
    """Build (t, x_full, xdot_dyn) -> dynamic residual for the residual monitor."""
    theta_dm = ca.DM([theta[p] for p in model.parameters])
    dynamic_rows, _ = _row_split(residual, model)
    n_exo = len(model.exogenous)

    def f(t: float, x_full: np.ndarray, xdot_dyn: np.ndarray) -> np.ndarray:
        out = residual.function(ca.DM(xdot_dyn), ca.DM(x_full), ca.DM.zeros(n_exo, 1), theta_dm, t)
        full = np.array(out).reshape(-1)
        return full[dynamic_rows]

    return f


def test_residual_defect_small_on_a_resolved_solution():
    m = _model(DECAY)
    residual = build_residual(m)
    theta = evaluate_parameters(m)
    fine = solve_pf(m, horizon=2.0, intervals=200)
    err = select_monitor("residual").assess(
        MonitorInput(
            grid=uniform_grid(2.0, 200),
            path=fine.path,
            dynamic_residual=_dynamic_residual(m, residual, theta),
            n_dynamic=1,
        )
    )
    assert err.per_interval.shape == (200,)
    assert err.estimate < 1e-2  # a well-resolved smooth path has a small defect


def test_residual_defect_shrinks_with_refinement():
    m = _model(DECAY)
    residual = build_residual(m)
    theta = evaluate_parameters(m)
    f = _dynamic_residual(m, residual, theta)

    def defect(intervals: int) -> float:
        sol = solve_pf(m, horizon=2.0, intervals=intervals)
        err = select_monitor("residual").assess(
            MonitorInput(
                grid=uniform_grid(2.0, intervals),
                path=sol.path,
                dynamic_residual=f,
                n_dynamic=1,
            )
        )
        return err.estimate

    assert defect(80) < defect(20)


# --- surfaced in diagnostics ----------------------------------------------


def test_equidistribution_ratio_in_solution_diagnostics():
    sol = solve_pf(_model(DECAY), horizon=2.0, intervals=50)
    assert "equidistribution_ratio" in sol.diagnostics
    assert sol.diagnostics["equidistribution_ratio"] >= 1.0


def test_equidistribution_ratio_helper_handles_short_paths():
    assert equidistribution_ratio(np.array([0.0, 1.0]), np.zeros((2, 1))) == 1.0


def test_grid_error_ratio_is_one_for_uniform_indicator():
    err = GridError(per_interval=np.ones(8))
    assert err.equidistribution_ratio == pytest.approx(1.0)
    assert err.estimate is None

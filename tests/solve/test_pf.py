"""Tests for the perfect-foresight BVP driver.

The Crank–Nicolson scheme has closed-form discrete solutions for linear
models, so the solved path is checked exactly against them.
"""

from __future__ import annotations

import numpy as np
import pytest

from continuo.codegen.residual import build_residual
from continuo.ir import build
from continuo.parser import parse
from continuo.solve import SolveError, solve_pf
from continuo.solve.disc import mesh_from_points
from continuo.solve.pf import solve_segment
from continuo.solve.steady import evaluate_parameters


def model(src: str):
    return build(parse(src))


def cn_ratio(rate: float, dt: float) -> float:
    """The CN one-step factor for diff(z) = rate*z."""
    return (1 + rate * dt / 2) / (1 - rate * dt / 2)


# A linear saddle: stable state x (x(0) given), unstable jump y (y(T)=0).
SADDLE = """
var(state) x;
var(jump) y;
model;
  diff(x) = -x;
  diff(y) = y;
end;
initval;
  x = 1;
end;
"""


# --- exact discrete solution ----------------------------------------------


def test_linear_saddle_matches_cn_discrete_solution():
    sol = solve_pf(model(SADDLE), horizon=2.0, intervals=4)
    dt = 0.5
    ratio = cn_ratio(-1.0, dt)  # diff(x) = -x
    expected_x = np.array([ratio**i for i in range(5)])
    np.testing.assert_allclose(sol["x"], expected_x, atol=1e-9)
    np.testing.assert_allclose(sol["y"], np.zeros(5), atol=1e-9)


def test_linear_model_converges_in_one_newton_step():
    sol = solve_pf(model(SADDLE), horizon=2.0, intervals=8)
    assert sol.diagnostics["newton_iterations"] == 1  # Newton is exact for a linear system


def test_solution_shape_and_times():
    sol = solve_pf(model(SADDLE), horizon=10.0, intervals=20)
    assert sol.path.shape == (21, 2)
    assert sol.t[0] == 0.0
    assert sol.t[-1] == pytest.approx(10.0)
    assert sol.names == ("x", "y")


# --- algebraic variable ---------------------------------------------------


def test_algebraic_variable_tracked_pointwise():
    src = """
    var(state) x;
    var(jump) y;
    var z;
    model;
      diff(x) = -x;
      diff(y) = y;
      z = x + y;
    end;
    initval;
      x = 1;
    end;
    """
    sol = solve_pf(model(src), horizon=2.0, intervals=4)
    # z = x + y = x everywhere (y is zero).
    np.testing.assert_allclose(sol["z"], sol["x"], atol=1e-9)


# --- boundary conditions --------------------------------------------------


def test_initial_state_and_terminal_jump_pinned():
    sol = solve_pf(model(SADDLE), horizon=5.0, intervals=10)
    assert sol["x"][0] == pytest.approx(1.0)  # initval
    assert sol["y"][-1] == pytest.approx(0.0, abs=1e-9)  # terminal SS


def test_converges_to_nonzero_steady_state():
    # diff(x) = a - x has SS x* = a; over a long horizon the path reaches it.
    src = """
    var(state) x;
    var(jump) y;
    parameters a;
    a = 2;
    model;
      diff(x) = a - x;
      diff(y) = y;
    end;
    initval;
      x = 0;
    end;
    """
    sol = solve_pf(model(src), horizon=20.0, intervals=200)
    assert sol["x"][0] == pytest.approx(0.0)
    assert sol["x"][-1] == pytest.approx(2.0, abs=1e-3)


# --- exogenous ------------------------------------------------------------


def test_exogenous_shifts_the_path():
    src = """
    var(state) x;
    var(jump) y;
    varexo u;
    model;
      diff(x) = u - x;
      diff(y) = y;
    end;
    initval;
      x = 0;
    end;
    """
    sol = solve_pf(model(src), horizon=20.0, intervals=200, exogenous={"u": 3.0})
    assert sol["x"][-1] == pytest.approx(3.0, abs=1e-3)  # x* = u


# --- initval(steady) ------------------------------------------------------


def test_initval_steady_starts_at_steady_state():
    # Starting at the steady state, the path is flat at the SS.
    src = """
    var(state) x;
    var(jump) y;
    parameters a;
    a = 2;
    model;
      diff(x) = a - x;
      diff(y) = y;
    end;
    steady_state_model;
      x = a;
      y = 0;
    end;
    initval(steady);
    end;
    """
    sol = solve_pf(model(src), horizon=5.0, intervals=10)
    np.testing.assert_allclose(sol["x"], np.full(11, 2.0), atol=1e-9)


# A state x with steady state x* = u, driven by exogenous u. With u = 1 active
# from t=0, the e={…} override anchors x(0) at the u=0 SS instead. (solve_pf
# takes the constant exogenous directly; the shocks block is the orchestrator's.)
ANCHOR = """
var(state) x;
var(jump) y;
varexo u;
model;
  diff(x) = u - x;
  diff(y) = y;
end;
steady_state_model;
  x = u;
  y = 0;
end;
"""


def test_initval_steady_e_override_anchors_at_a_different_steady_state():
    src = ANCHOR + "initval(steady, e={u: 0});\nend;\n"
    sol = solve_pf(model(src), horizon=20.0, intervals=200, exogenous={"u": 1.0})
    assert sol["x"][0] == pytest.approx(0.0, abs=1e-9)  # anchored at the u=0 SS
    assert sol["x"][-1] == pytest.approx(1.0, abs=1e-3)  # to the active u=1 SS


def test_explicit_steady_state_e_override():
    # The same anchor written as an explicit per-state callable.
    src = ANCHOR + "initval;\n  x = steady_state(x, e={u: 0});\nend;\n"
    sol = solve_pf(model(src), horizon=20.0, intervals=200, exogenous={"u": 1.0})
    assert sol["x"][0] == pytest.approx(0.0, abs=1e-9)


def test_steady_state_override_default_is_the_active_exogenous():
    # No override: steady_state(x) is the active SS (x* = u = 1), so the path
    # is flat at 1.
    src = ANCHOR + "initval;\n  x = steady_state(x);\nend;\n"
    sol = solve_pf(model(src), horizon=10.0, intervals=50, exogenous={"u": 1.0})
    np.testing.assert_allclose(sol["x"], np.full(51, 1.0), atol=1e-6)


# --- errors ---------------------------------------------------------------


def test_steady_state_override_rejects_non_exogenous_key():
    src = ANCHOR + "initval(steady, e={a: 0});\nend;\n"
    with pytest.raises(SolveError, match="not an exogenous variable"):
        solve_pf(model(src), horizon=5.0, intervals=10, exogenous={"u": 1.0})


def test_missing_initval_rejected():
    src = "var(state) x;\nvar(jump) y;\nmodel;\n  diff(x) = -x;\n  diff(y) = y;\nend;"
    with pytest.raises(SolveError, match="no initial value"):
        solve_pf(model(src), horizon=2.0, intervals=4)


# --- collocation schemes --------------------------------------------------

# A linear scalar IVP with the analytic solution K(t) = exp(lam*t).
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


def _max_error(scheme: str, order: int | None, intervals: int, horizon: float) -> float:
    sol = solve_pf(model(DECAY), horizon=horizon, intervals=intervals, scheme=scheme, order=order)
    return float(np.max(np.abs(sol["K"] - np.exp(_LAM * sol.t))))


@pytest.mark.parametrize(
    "scheme,order,expected",
    [
        ("crank_nicolson", None, 2),
        ("gauss", 4, 4),
        ("gauss", 6, 6),
        ("radau", 3, 3),
        ("radau", 5, 5),
        ("lobatto_iiia", 4, 4),
    ],
)
def test_collocation_convergence_order(scheme, order, expected):
    # Halving dt should cut the error by ~2**order; measure the rate on the
    # finer pair (well inside the asymptotic regime, above the round-off floor).
    horizon = 2.0
    base = 4 if expected <= 4 else 3
    errors = [_max_error(scheme, order, base * k, horizon) for k in (1, 2, 4)]
    rate = np.log2(errors[1] / errors[2])
    assert rate == pytest.approx(expected, abs=0.5)


def test_collocation_matches_crank_nicolson_on_a_nonlinear_model():
    # A nonlinear RBC transition: every scheme agrees with CN at a fine grid.
    src = """
    var(state) K;
    var(jump) C;
    parameters rho, alpha, delta;
    rho = 0.03;
    alpha = 0.33;
    delta = 0.1;
    model;
      diff(K) = K^alpha - delta * K - C;
      diff(C) = C * (alpha * K^(alpha - 1) - delta - rho);
    end;
    initval;
      K = 0.8 * steady_state(K);
    end;
    """
    m = model(src)
    ref = solve_pf(m, horizon=40.0, intervals=400)
    for scheme in ("gauss", "radau", "lobatto_iiia"):
        sol = solve_pf(m, horizon=40.0, intervals=400, scheme=scheme)
        assert np.max(np.abs(sol["K"] - ref["K"])) < 1e-4
        assert np.max(np.abs(sol["C"] - ref["C"])) < 1e-4


def test_collocation_solution_has_node_shape():
    # The returned path is the node block only; stage unknowns are dropped.
    sol = solve_pf(model(DECAY), horizon=2.0, intervals=10, scheme="radau", order=5)
    assert sol.path.shape == (11, 1)


def test_unsupported_order_rejected():
    with pytest.raises(SolveError, match="order"):
        solve_pf(model(DECAY), horizon=2.0, intervals=10, scheme="gauss", order=3)


# --- non-uniform grid -----------------------------------------------------


@pytest.mark.parametrize("scheme,order", [("crank_nicolson", None), ("radau", 5)])
def test_non_uniform_grid_solves_pure_ode(scheme, order):
    # A graded mesh (dense near t=0) must still recover K(t) = exp(lam*t).
    m = model(DECAY)
    residual = build_residual(m)
    theta = evaluate_parameters(m)
    t_horizon = 2.0
    grid = mesh_from_points(t_horizon * np.linspace(0.0, 1.0, 21) ** 2)
    assert grid.steps.max() > 3 * grid.steps.min()  # genuinely non-uniform
    path, _iters, _sym, _num = solve_segment(
        m,
        residual,
        grid,
        theta=theta,
        exogenous_at=lambda _t: {},
        initial_states={"K": 1.0},
        terminal_jumps={},
        guess=np.ones((grid.intervals + 1, 1)),
        scheme=scheme,
        order=order,
    )
    exact = np.exp(_LAM * grid.points)
    assert np.max(np.abs(path[:, 0] - exact)) < 1e-3

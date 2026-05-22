"""Tests for the perfect-foresight BVP driver.

The Crank–Nicolson scheme has closed-form discrete solutions for linear
models, so the solved path is checked exactly against them.
"""

from __future__ import annotations

import numpy as np
import pytest

from dynare_ct.ir import build
from dynare_ct.parser import parse
from dynare_ct.solve import SolveError, solve_pf


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


# --- errors ---------------------------------------------------------------


def test_missing_initval_rejected():
    src = "var(state) x;\nvar(jump) y;\nmodel;\n  diff(x) = -x;\n  diff(y) = y;\nend;"
    with pytest.raises(SolveError, match="no initial value"):
        solve_pf(model(src), horizon=2.0, intervals=4)

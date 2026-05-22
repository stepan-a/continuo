"""Tests for the simulation orchestrator."""

from __future__ import annotations

import numpy as np
import pytest

from continuo.ir import build
from continuo.parser import parse
from continuo.solve import SolveError, simulate, solve_pf


def model(src: str):
    return build(parse(src))


# x tracks the exogenous u (x* = u); y is a decoupled jump anchored at 0.
TRACKER = """
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

# A bare linear saddle (no shocks); the command is appended per test.
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


# --- reading the simulate command -----------------------------------------


def test_reads_horizon_and_grid_from_command():
    sol = simulate(model(SADDLE + "simulate(T=10, N=50);"))
    assert sol.path.shape == (51, 2)
    assert sol.t[-1] == pytest.approx(10.0)


def test_explicit_arguments_override_command():
    sol = simulate(model(SADDLE + "simulate(T=10, N=50);"), horizon=4.0, intervals=8)
    assert sol.path.shape == (9, 2)
    assert sol.t[-1] == pytest.approx(4.0)


def test_no_command_and_no_arguments_rejected():
    with pytest.raises(SolveError, match="no simulate command"):
        simulate(model(SADDLE))


# --- constant shock matches the explicit solve ----------------------------


def test_constant_shock_matches_solve_pf():
    src = TRACKER + "shocks;\n  var u;\n  path = 2;\nend;\nsimulate(T=20, N=200);"
    orchestrated = simulate(model(src))
    direct = solve_pf(model(TRACKER), horizon=20.0, intervals=200, exogenous={"u": 2.0})
    np.testing.assert_allclose(orchestrated["x"], direct["x"], atol=1e-9)
    assert orchestrated["x"][-1] == pytest.approx(2.0, abs=1e-3)  # x* = u


def test_no_shocks_is_autonomous():
    src = SADDLE + "simulate(T=2, N=4);"
    sol = simulate(model(src))
    direct = solve_pf(model(src), horizon=2.0, intervals=4)
    np.testing.assert_allclose(sol["x"], direct["x"], atol=1e-12)


# --- time-varying (anticipated step) shock --------------------------------


def test_anticipated_step_shock():
    # u steps from 0 to 1 at t=5; x tracks it. Terminal SS uses e(T)=1.
    src = TRACKER + "shocks;\n  var u;\n  path = if(t >= 5, 1, 0);\nend;\nsimulate(T=20, N=200);"
    sol = simulate(model(src))
    x = sol["x"]
    assert x[0] == pytest.approx(0.0)  # initval
    assert x[-1] == pytest.approx(1.0, abs=1e-3)  # x* = u(T) = 1
    # Before the step the forcing is zero, so x stays near 0; after, it rises.
    before = sol.t <= 4.0
    after = sol.t >= 10.0
    assert np.all(x[before] < 0.05)
    assert np.all(x[after] > 0.6)


def test_pulse_helper_in_a_shock_path():
    # u is on (=1) only over the window [5, 10); x tracks it up then back down.
    src = TRACKER + "shocks;\n  var u;\n  path = pulse(t, 5, 10);\nend;\nsimulate(T=30, N=300);"
    sol = simulate(model(src))
    x = sol["x"]
    assert np.all(x[sol.t <= 4.0] < 0.05)  # quiet before the pulse
    assert x[np.argmin(np.abs(sol.t - 9.5))] > 0.6  # risen during the pulse
    assert x[-1] == pytest.approx(0.0, abs=1e-3)  # decayed back after it ends


# --- surprise (multi-segment) ---------------------------------------------


# u is believed to be 0.5 forever; at t=5 agents are surprised by u = 1.
# x (initval 0) heads toward the old SS 0.5, then toward the new SS 1.
SURPRISE = (
    TRACKER + "shocks;\n  var u;\n  path = 0.5;\n  path at t=5 = 1;\nend;\nsimulate(T=20, N=200);"
)


def test_mit_surprise_shock():
    x = simulate(model(SURPRISE))["x"]
    assert x[0] == pytest.approx(0.0)  # initval
    assert x[-1] == pytest.approx(1.0, abs=1e-3)  # new steady state after the surprise
    assert np.all(np.diff(x) > -1e-9)  # u only rises, so x is non-decreasing
    assert 0.4 < x[50] < 0.5  # under the old belief x is heading to 0.5 at t=5


def test_state_is_continuous_across_the_surprise():
    sol = simulate(model(SURPRISE))
    x = sol["x"]
    reveal = 50  # grid index of t=5 (dt = 0.1)
    # The state does not jump at the surprise; it continues from its level.
    assert x[reveal] == pytest.approx(x[reveal - 1], abs=1e-3)
    # ... and then climbs toward the new steady state.
    assert x[reveal + 20] > x[reveal] + 0.1


def test_multiple_surprises():
    # u: believed 0, surprised to 1 at t=5, then to 2 at t=10 (three segments).
    src = (
        TRACKER + "shocks;\n  var u;\n  path = 0;\n  path at t=5 = 1;\n  path at t=10 = 2;\nend;\n"
        "simulate(T=20, N=200);"
    )
    x = simulate(model(src))["x"]
    dt = 0.1
    assert x[0] == pytest.approx(0.0)
    assert np.all(x[: int(5 / dt)] < 0.05)  # flat at 0 before the first surprise
    assert x[int(10 / dt)] == pytest.approx(1.0, abs=0.05)  # near the first new SS at t=10
    assert x[-1] == pytest.approx(2.0, abs=1e-3)  # converged to the second new SS
    # State continuous across the second surprise too.
    second = int(10 / dt)
    assert x[second] == pytest.approx(x[second - 1], abs=1e-3)


# --- deferred features -----------------------------------------------------


def test_unimplemented_scheme_rejected():
    src = SADDLE + "simulate(T=2, N=4, scheme=radau);"
    with pytest.raises(SolveError, match="not implemented"):
        simulate(model(src))

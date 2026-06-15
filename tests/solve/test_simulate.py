"""Tests for the simulation orchestrator."""

from __future__ import annotations

import numpy as np
import pytest

from continuo.ir import build
from continuo.parser import parse
from continuo.solve import SolveError, available_solvers, simulate, solve_pf

# Optional backends present in this environment, exercised by the cross-checks
# below; superlu is always available and is the reference.
OPTIONAL_BACKENDS = sorted(available_solvers() - {"superlu"})


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


def test_steady_e_override_anchors_initial_state():
    # u = 1 is in effect from t=0 (a change already live); the e={…} override
    # anchors the initial state at the pre-change (u=0) steady state.
    src = (
        "var(state) x;\nvar(jump) y;\nvarexo u;\n"
        "model;\n  diff(x) = u - x;\n  diff(y) = y;\nend;\n"
        "steady_state_model;\n  x = u;\n  y = 0;\nend;\n"
        "initval(steady, e={u: 0});\nend;\n"
        "shocks;\n  var u;\n  path = 1;\nend;\n"
        "simulate(T=20, N=200);"
    )
    sol = simulate(model(src))
    assert sol["x"][0] == pytest.approx(0.0, abs=1e-9)  # anchored at the u=0 SS
    assert sol["x"][-1] == pytest.approx(1.0, abs=1e-3)  # to the active u=1 SS


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


def test_state_continuous_across_each_surprise_in_a_chain():
    # The existing 3-segment test pins continuity at the second surprise only;
    # this one pins it at the first too, so a regression in the state-carry
    # between segment 0 and segment 1 is caught.
    src = (
        TRACKER + "shocks;\n  var u;\n  path = 0;\n  path at t=5 = 1;\n  path at t=10 = 2;\nend;\n"
        "simulate(T=20, N=200);"
    )
    sol = simulate(model(src))
    x = sol["x"]
    dt = 0.1
    first, second = int(5 / dt), int(10 / dt)
    assert len(sol.segments) == 3
    assert x[first] == pytest.approx(x[first - 1], abs=1e-3)
    assert x[second] == pytest.approx(x[second - 1], abs=1e-3)


# --- reveal-time snapping --------------------------------------------------


def test_reveal_time_snaps_to_nearest_grid_point():
    # dt = 0.1; reveal at t=5.07 is closer to index 51 (t=5.1) than to index 50.
    src = (
        TRACKER + "shocks;\n  var u;\n  path = 0;\n  path at t=5.07 = 1;\nend;\n"
        "simulate(T=20, N=200);"
    )
    sol = simulate(model(src))
    assert len(sol.segments) == 2
    assert sol.segments[1].start_time == pytest.approx(5.1)


def test_reveal_time_at_half_grid_point_uses_banker_rounding():
    # dt = 1.0; Python's round() rounds half-to-even, so t=2.5 → 2 and t=3.5 → 4.
    # This test pins that contract: a switch to "round half up" would break it.
    src_25 = (
        TRACKER + "shocks;\n  var u;\n  path = 0;\n  path at t=2.5 = 1;\nend;\n"
        "simulate(T=10, N=10);"
    )
    src_35 = (
        TRACKER + "shocks;\n  var u;\n  path = 0;\n  path at t=3.5 = 1;\nend;\n"
        "simulate(T=10, N=10);"
    )
    assert simulate(model(src_25)).segments[1].start_time == pytest.approx(2.0)
    assert simulate(model(src_35)).segments[1].start_time == pytest.approx(4.0)


def test_reveal_snapped_to_grid_index_zero_does_not_create_extra_segment():
    # dt = 0.1; reveal at t=0.03 rounds to index 0, which _segment_starts filters
    # out (0 < index < intervals). The single segment runs under the new belief.
    src = (
        TRACKER + "shocks;\n  var u;\n  path = 0;\n  path at t=0.03 = 1;\nend;\n"
        "simulate(T=20, N=200);"
    )
    sol = simulate(model(src))
    assert len(sol.segments) == 1
    assert sol.segments[0].info_set["u"] == pytest.approx(1.0)


# --- deferred features -----------------------------------------------------


def test_unimplemented_scheme_rejected():
    src = SADDLE + "simulate(T=2, N=4, scheme=radau);"
    with pytest.raises(SolveError, match="not implemented"):
        simulate(model(src))


# --- linear-solver selection ----------------------------------------------


def test_solver_preset_threads_through_and_is_recorded():
    src = SADDLE + "simulate(T=2, N=4);"
    sol = simulate(model(src), solver="superlu")
    assert sol.diagnostics["solver"] == "superlu"
    np.testing.assert_allclose(sol["x"], simulate(model(src))["x"], atol=1e-12)


def test_solver_auto_is_the_default():
    src = SADDLE + "simulate(T=2, N=4);"
    assert simulate(model(src)).diagnostics["solver"] == "superlu"


def test_solver_instance_is_accepted():
    from continuo.solve import SuperluSolver

    src = SADDLE + "simulate(T=2, N=4);"
    sol = simulate(model(src), solver=SuperluSolver())
    assert sol.diagnostics["solver"] == "superlu"


def test_solver_threads_through_each_segment_of_a_surprise():
    sol = simulate(model(SURPRISE), solver="superlu")
    assert len(sol.segments) == 2
    np.testing.assert_allclose(sol["x"], simulate(model(SURPRISE))["x"], atol=1e-12)


def test_unknown_solver_rejected():
    src = SADDLE + "simulate(T=2, N=4);"
    with pytest.raises(SolveError, match="unknown linear solver"):
        simulate(model(src), solver="nope")


def test_solve_pf_records_the_solver():
    sol = solve_pf(model(SADDLE), horizon=2.0, intervals=4, solver="superlu")
    assert sol.diagnostics["solver"] == "superlu"


# --- cross-checks: every available backend agrees with superlu -------------


@pytest.mark.skipif(not OPTIONAL_BACKENDS, reason="no optional backends installed")
@pytest.mark.parametrize("backend", OPTIONAL_BACKENDS)
def test_backend_matches_superlu_on_a_transition(backend):
    src = TRACKER + "shocks;\n  var u;\n  path = 2;\nend;\nsimulate(T=20, N=200);"
    ref = simulate(model(src), solver="superlu")
    got = simulate(model(src), solver=backend)
    assert got.diagnostics["solver"] == backend
    np.testing.assert_allclose(got["x"], ref["x"], atol=1e-9)
    np.testing.assert_allclose(got["y"], ref["y"], atol=1e-9)


@pytest.mark.skipif(not OPTIONAL_BACKENDS, reason="no optional backends installed")
@pytest.mark.parametrize("backend", OPTIONAL_BACKENDS)
def test_backend_matches_superlu_across_a_surprise(backend):
    ref = simulate(model(SURPRISE), solver="superlu")
    got = simulate(model(SURPRISE), solver=backend)
    assert len(got.segments) == 2
    np.testing.assert_allclose(got["x"], ref["x"], atol=1e-9)

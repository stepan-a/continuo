"""Tests for adaptive mesh refinement (simulate(adapt=tol)).

Driven through the orchestrator at the Python level; the directive / CLI
surface comes later.
"""

from __future__ import annotations

import numpy as np
import pytest

from continuo.ir import build
from continuo.parser import parse
from continuo.solve import SolveError
from continuo.solve.orchestrator import simulate

# A scalar decay with a sharp transient and a long flat tail — exactly the
# shape where concentrating nodes near t=0 beats a uniform mesh. Analytic
# solution K(t) = exp(lam*t).
_LAM = -3.0
_T = 10.0
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


def _model(src: str = DECAY):
    return build(parse(src))


def _max_error(sol) -> float:
    return float(np.max(np.abs(sol["K"] - np.exp(_LAM * sol.t))))


@pytest.mark.parametrize("monitor", ["richardson", "residual"])
def test_adaptive_reaches_the_tolerance(monitor):
    sol = simulate(_model(), horizon=_T, intervals=20, adapt=1e-3, monitor=monitor)
    assert _max_error(sol) < 1e-3


@pytest.mark.parametrize("monitor", ["richardson", "residual"])
def test_adaptive_beats_uniform_at_equal_node_budget(monitor):
    # Adaptive places nodes where the path bends; at the same node count a
    # uniform mesh is less accurate.
    adapted = simulate(_model(), horizon=_T, intervals=20, adapt=1e-3, monitor=monitor)
    uniform = simulate(_model(), horizon=_T, intervals=len(adapted.t) - 1)
    assert len(uniform.t) == len(adapted.t)
    assert _max_error(adapted) < _max_error(uniform)


def test_adaptive_concentrates_nodes_near_the_transient():
    sol = simulate(_model(), horizon=_T, intervals=20, adapt=1e-3)
    steps = np.diff(sol.t)
    # the first step (near the sharp t=0 transient) is much smaller than the last
    assert steps[0] < 0.25 * steps[-1]


def test_adaptive_works_under_crank_nicolson():
    sol = simulate(_model(), horizon=_T, intervals=20, adapt=1e-3, scheme="crank_nicolson")
    assert _max_error(sol) < 1e-3


def test_adaptive_default_path_is_uniform():
    # Without adapt the mesh stays uniform (regression guard).
    sol = simulate(_model(), horizon=_T, intervals=40)
    assert np.allclose(np.diff(sol.t), _T / 40)


def test_adapt_requires_an_estimating_monitor():
    with pytest.raises(SolveError, match="error-estimating monitor"):
        simulate(_model(), horizon=_T, intervals=20, adapt=1e-3, monitor="curvature")


def test_adaptive_higher_order_scheme():
    # Adaptivity composes with a collocation family.
    sol = simulate(_model(), horizon=_T, intervals=20, adapt=1e-6, scheme="radau", order=5)
    assert _max_error(sol) < 1e-5


def test_adaptive_multi_segment_with_a_shock():
    # A reveal splits the horizon; each segment is refined independently and the
    # reveal stays an exact node.
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
    shocks;
      var u;
      path at t=0 = 0;
      path at t=3.3 = 1;
    end;
    simulate(T=20, N=40);
    """
    sol = simulate(_model(src), adapt=1e-4)
    assert len(sol.segments) == 2
    assert np.any(np.isclose(sol.t, 3.3))  # the reveal is an exact node
    assert sol["x"][-1] == pytest.approx(1.0, abs=1e-2)  # x -> u = 1

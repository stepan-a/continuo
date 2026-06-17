"""Tests for the command-validation pass: simulate and steady."""

from __future__ import annotations

import pytest

from continuo.ir import IRError, build
from continuo.parser import parse

HEADER = """
var(state) K;
var Y;
parameters alpha;
alpha = 0.33;
model;
  diff(K) = Y - K;
  Y = K^alpha;
end;
"""


def ir(extra: str = ""):
    return build(parse(HEADER + extra))


# --- simulate -------------------------------------------------------------


def test_simulate_collected():
    m = ir("simulate(T=200, N=400);")
    (sim,) = m.simulations
    assert sim.horizon.value == 200.0
    assert sim.grid.value == 400.0
    assert sim.scheme == "crank_nicolson"  # default


def test_simulate_scheme_override():
    m = ir("simulate(T=200, N=400, scheme=radau);")
    assert m.simulations[0].scheme == "radau"


def test_simulate_solver_defaults_to_none():
    assert ir("simulate(T=200, N=400);").simulations[0].solver is None


def test_simulate_solver_directive_as_identifier():
    assert ir("simulate(T=200, N=400, solver=klu);").simulations[0].solver == "klu"


def test_simulate_solver_directive_as_string_for_dashed_preset():
    m = ir('simulate(T=200, N=400, solver="klu-nobtf");')
    assert m.simulations[0].solver == "klu-nobtf"


def test_simulate_rejects_unknown_solver():
    with pytest.raises(IRError, match="unknown linear solver 'magic'"):
        ir("simulate(T=200, N=400, solver=magic);")


def test_no_command_leaves_empty():
    m = ir()
    assert m.simulations == ()
    assert m.steady_queries == ()


def test_simulate_requires_horizon():
    with pytest.raises(IRError, match="requires the horizon T"):
        ir("simulate(N=400);")


def test_simulate_requires_grid():
    with pytest.raises(IRError, match="requires the grid resolution N"):
        ir("simulate(T=200);")


def test_simulate_rejects_unknown_option():
    with pytest.raises(IRError, match="unknown simulate option 'foo'"):
        ir("simulate(T=200, N=400, foo=1);")


def test_simulate_rejects_unknown_scheme():
    with pytest.raises(IRError, match="unknown discretisation scheme 'rk4'"):
        ir("simulate(T=200, N=400, scheme=rk4);")


def test_simulate_rejects_positional_argument():
    with pytest.raises(IRError, match="keyword arguments only"):
        ir("simulate(200, 400);")


def test_simulate_rejects_non_positive_horizon():
    with pytest.raises(IRError, match="T must be positive"):
        ir("simulate(T=0, N=400);")


def test_simulate_rejects_non_integer_grid():
    with pytest.raises(IRError, match="N must be a positive integer"):
        ir("simulate(T=200, N=400.5);")


def test_simulate_rejects_negative_grid():
    with pytest.raises(IRError, match="N must be a positive integer"):
        ir("simulate(T=200, N=-10);")


def test_simulate_duplicate_option_rejected():
    with pytest.raises(IRError, match="duplicate simulate option 'T'"):
        ir("simulate(T=200, N=400, T=300);")


def test_parametric_horizon_flows_through():
    # T given as a parameter: present, but the numeric check is deferred.
    m = ir("parameters horizon;\n  horizon = 200;\nsimulate(T=horizon, N=400);")
    assert m.simulations[0].horizon.name == "horizon"


# --- steady ---------------------------------------------------------------


def test_bare_steady():
    m = ir("steady;")
    (query,) = m.steady_queries
    assert query.time is None
    assert query.exogenous is None


def test_steady_with_time():
    m = ir("steady(t=5);")
    assert m.steady_queries[0].time.value == 5.0


def test_steady_with_exogenous():
    m = ir("steady(t=0, e={alpha: 0.4});")
    query = m.steady_queries[0]
    assert query.time.value == 0.0
    assert query.exogenous is not None


def test_steady_rejects_negative_time():
    with pytest.raises(IRError, match="t must be non-negative"):
        ir("steady(t=-1);")


def test_steady_rejects_unknown_option():
    with pytest.raises(IRError, match="unknown steady option 'bogus'"):
        ir("steady(bogus=1);")


def test_steady_e_must_be_mapping():
    with pytest.raises(IRError, match="'e' must be a"):
        ir("steady(e=5);")


def test_steady_solver_defaults_to_none():
    assert ir("steady;").steady_queries[0].solver is None


def test_steady_solver_as_identifier():
    assert ir("steady(solver=newton);").steady_queries[0].solver == "newton"


def test_steady_solver_as_string_for_dashed_preset():
    assert ir('steady(solver="df-sane");').steady_queries[0].solver == "df-sane"


def test_steady_rejects_unknown_solver():
    with pytest.raises(IRError, match="unknown steady-state solver 'magic'"):
        ir("steady(solver=magic);")


def test_steady_options_parsed():
    m = ir('steady(solver=kinsol, options={strategy: "picard", steps: 20});')
    q = m.steady_queries[0]
    assert q.solver == "kinsol"
    assert q.options == {"strategy": "picard", "steps": 20}


def test_steady_options_bare_identifier_value():
    q = ir("steady(solver=kinsol, options={strategy: picard});").steady_queries[0]
    assert q.options == {"strategy": "picard"}


def test_steady_options_keeps_float():
    q = ir("steady(solver=hybr, options={factor: 0.1});").steady_queries[0]
    assert q.options == {"factor": 0.1}


def test_steady_options_default_none():
    assert ir("steady(solver=newton);").steady_queries[0].options is None


def test_steady_options_requires_solver():
    with pytest.raises(IRError, match="options requires a solver"):
        ir("steady(options={strategy: picard});")


def test_steady_options_must_be_mapping():
    with pytest.raises(IRError, match="options must be a"):
        ir("steady(solver=kinsol, options=5);")


# --- the nodomain flag ----------------------------------------------------


def test_steady_nodomain_defaults_false():
    assert ir("steady;").steady_queries[0].nodomain is False


def test_steady_nodomain_flag_parsed():
    assert ir("steady(nodomain);").steady_queries[0].nodomain is True


def test_steady_nodomain_combines_with_kwargs():
    q = ir("steady(t=5, nodomain, solver=newton);").steady_queries[0]
    assert q.nodomain is True
    assert q.time.value == 5.0
    assert q.solver == "newton"


def test_steady_rejects_unknown_flag():
    with pytest.raises(IRError, match="unknown steady flag 'bogus'"):
        ir("steady(bogus);")


def test_steady_rejects_duplicate_flag():
    with pytest.raises(IRError, match="duplicate steady flag 'nodomain'"):
        ir("steady(nodomain, nodomain);")


# --- multiple commands ----------------------------------------------------


def test_multiple_commands_collected_in_order():
    m = ir("steady(t=0);\nsimulate(T=200, N=400);\nsteady;")
    assert len(m.steady_queries) == 2
    assert len(m.simulations) == 1

"""Tests for the boundary-data pass: initval and initial_guess."""

from __future__ import annotations

import pytest

from continuo.ir import IRError, build
from continuo.parser import parse
from continuo.parser.ast import FunctionCall, NumberLit

# A first-order model with two states (K, A), one jump (C), one algebraic (Y).
HEADER = """
var(state) K, A;
var(jump) C;
var Y;
varexo eps;
parameters alpha;
alpha = 0.33;
model;
  diff(K) = Y - C;
  diff(A) = eps - A;
  diff(C) = C * (Y - alpha);
  Y = K^alpha + A;
end;
"""


def ir(extra: str = ""):
    return build(parse(HEADER + extra))


# --- initval collection ---------------------------------------------------


def test_initval_collects_state_values():
    m = ir("initval; K = 10; A = 1; end;")
    assert set(m.initial_values) == {"K", "A"}
    assert isinstance(m.initial_values["K"], NumberLit)


def test_no_initval_block_still_builds():
    m = ir()
    assert m.initial_values == {}


def test_initval_value_can_be_an_expression():
    m = ir("initval; K = steady_state(K); A = 2 * alpha; end;")
    assert isinstance(m.initial_values["K"], FunctionCall)


# --- initval completeness and LHS rules -----------------------------------


def test_missing_state_rejected():
    with pytest.raises(IRError, match="state 'A' has no initial value"):
        ir("initval; K = 10; end;")


def test_jump_in_initval_rejected():
    with pytest.raises(IRError, match="only states may appear in initval; 'C' is a jump"):
        ir("initval; K = 1; A = 1; C = 1; end;")


def test_algebraic_in_initval_rejected():
    with pytest.raises(IRError, match="'Y' is algebraic"):
        ir("initval; K = 1; A = 1; Y = 1; end;")


def test_exogenous_in_initval_rejected():
    with pytest.raises(IRError, match="'eps' is exogenous"):
        ir("initval; K = 1; A = 1; eps = 1; end;")


def test_parameter_in_initval_rejected():
    with pytest.raises(IRError, match="'alpha' is a parameter"):
        ir("initval; K = 1; A = 1; alpha = 1; end;")


def test_duplicate_initial_value_rejected():
    with pytest.raises(IRError, match="duplicate initial value for 'K'"):
        ir("initval; K = 1; A = 1; K = 2; end;")


# --- initval(steady) sugar ------------------------------------------------


def test_steady_fills_all_states():
    m = ir("initval(steady); end;")
    assert set(m.initial_values) == {"K", "A"}
    for value in m.initial_values.values():
        assert isinstance(value, FunctionCall) and value.name.name == "steady_state"


def test_steady_with_override():
    m = ir("initval(steady); K = 5; end;")
    assert isinstance(m.initial_values["K"], NumberLit)  # explicit override
    assert isinstance(m.initial_values["A"], FunctionCall)  # auto-filled


def test_steady_threads_e_override():
    m = ir("initval(steady, e={alpha: 0.4}); end;")
    call = m.initial_values["K"]
    assert call.name.name == "steady_state"
    assert [kw.name.name for kw in call.kwargs] == ["e"]


def test_steady_rejects_unknown_argument():
    with pytest.raises(IRError, match="unknown initval.steady. argument 'foo'"):
        ir("initval(steady, foo=1); end;")


# --- higher-order: diff(x) initial conditions -----------------------------

HO_HEADER = """
var(state) x;
var Y;
model;
  diff(x, 2) = Y - x;
  Y = x;
end;
"""


def ho(extra: str):
    return build(parse(HO_HEADER + extra))


def test_higher_order_diff_initial_condition_maps_to_aux():
    m = ho("initval; x = 1; diff(x) = 0.5; end;")
    assert set(m.initial_values) == {"x", "__aux_diff_x_1"}
    assert isinstance(m.initial_values["__aux_diff_x_1"], NumberLit)


def test_higher_order_missing_derivative_condition_rejected():
    with pytest.raises(IRError, match=r"diff\(x\)' has no initial value"):
        ho("initval; x = 1; end;")


def test_diff_initval_on_first_order_state_rejected():
    # K is first order, so diff(K) has no auxiliary slot.
    with pytest.raises(IRError, match="has no initial condition"):
        ir("initval; K = 1; A = 1; diff(K) = 1; end;")


def test_steady_fills_aux_with_zero():
    m = ho("initval(steady); end;")
    assert isinstance(m.initial_values["__aux_diff_x_1"], NumberLit)
    assert m.initial_values["__aux_diff_x_1"].value == 0.0
    assert isinstance(m.initial_values["x"], FunctionCall)  # steady_state(x)


# --- initial_guess --------------------------------------------------------


def test_initial_guess_collected():
    m = ir("initval; K = 1; A = 1; end;\ninitial_guess; C = 0.8; Y = 1.2; end;")
    assert set(m.initial_guess) == {"C", "Y"}


def test_initial_guess_need_not_be_complete():
    m = ir("initval; K = 1; A = 1; end;\ninitial_guess; C = 0.8; end;")
    assert set(m.initial_guess) == {"C"}


def test_initial_guess_for_non_endogenous_rejected():
    with pytest.raises(IRError, match="not an endogenous variable"):
        ir("initval; K = 1; A = 1; end;\ninitial_guess; alpha = 1; end;")


def test_duplicate_initial_guess_rejected():
    with pytest.raises(IRError, match="duplicate initial_guess for 'C'"):
        ir("initval; K = 1; A = 1; end;\ninitial_guess; C = 1; C = 2; end;")


# --- duplicate blocks -----------------------------------------------------


def test_multiple_initval_blocks_rejected():
    with pytest.raises(IRError, match="more than one initval block"):
        ir("initval; K = 1; A = 1; end;\ninitval; K = 2; A = 2; end;")

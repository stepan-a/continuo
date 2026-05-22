"""Tests for the steady_state_model validation pass."""

from __future__ import annotations

import pytest

from dynare_ct.ir import IRError, build
from dynare_ct.parser import parse
from dynare_ct.parser.ast import NumberLit

# Two states (K, A), one jump (C), one algebraic (Y).
HEADER = """
var(state) K, A;
var(jump) C;
var Y;
varexo eps;
parameters alpha, delta;
alpha = 0.33;
delta = 0.025;
model;
  diff(K) = Y - C;
  diff(A) = eps - A;
  diff(C) = C * (Y - alpha);
  Y = K^alpha + A;
end;
"""

COMPLETE = """
steady_state_model;
  K = (alpha / delta)^(1 / (1 - alpha));
  A = eps;
  Y = K^alpha + A;
  C = Y - delta * K;
end;
"""


def ir(extra: str = ""):
    return build(parse(HEADER + extra))


# --- collection -----------------------------------------------------------


def test_steady_state_collected():
    m = ir(COMPLETE)
    assert set(m.steady_state) == {"K", "A", "Y", "C"}


def test_absent_block_leaves_steady_state_empty():
    m = ir()
    assert m.steady_state == {}


def test_rhs_may_reference_other_endogenous_and_exogenous():
    # A = eps (exogenous on RHS); Y = K^alpha + A (endogenous on RHS).
    m = ir(COMPLETE)
    assert "Y" in m.steady_state


# --- LHS rules ------------------------------------------------------------


def test_varexo_on_lhs_rejected():
    block = "steady_state_model;\n  K = 1; A = 1; Y = 1; C = 1; eps = 1;\nend;"
    with pytest.raises(IRError, match="'eps' is exogenous"):
        ir(block)


def test_parameter_on_lhs_rejected():
    block = "steady_state_model;\n  K = 1; A = 1; Y = 1; C = 1; alpha = 1;\nend;"
    with pytest.raises(IRError, match="'alpha' is a parameter"):
        ir(block)


def test_undeclared_on_lhs_rejected():
    block = "steady_state_model;\n  K = 1; A = 1; Y = 1; C = 1; Z = 1;\nend;"
    with pytest.raises(IRError, match="undeclared variable 'Z'"):
        ir(block)


def test_non_identifier_lhs_rejected():
    block = "steady_state_model;\n  K = 1; A = 1; Y = 1; diff(C) = 1;\nend;"
    with pytest.raises(IRError, match="must be a variable name"):
        ir(block)


# --- completeness ---------------------------------------------------------


def test_incomplete_block_rejected():
    block = "steady_state_model;\n  K = 1; A = 1; Y = 1;\nend;"  # C missing
    with pytest.raises(IRError, match="incomplete: no definition for C"):
        ir(block)


def test_incomplete_lists_all_missing():
    block = "steady_state_model;\n  K = 1; A = 1;\nend;"  # C and Y missing
    with pytest.raises(IRError, match="C, Y"):  # reported in declaration order
        ir(block)


def test_duplicate_definition_rejected():
    block = "steady_state_model;\n  K = 1; A = 1; Y = 1; C = 1; K = 2;\nend;"
    with pytest.raises(IRError, match="duplicate steady_state_model definition for 'K'"):
        ir(block)


# --- higher-order auxiliaries ---------------------------------------------

HO = """
var(state) x;
var Y;
model;
  diff(x, 2) = Y - x;
  Y = x;
end;
steady_state_model;
  x = 0;
  Y = 0;
end;
"""


def test_aux_states_filled_with_zero():
    m = build(parse(HO))
    # The user defines x and Y; the auxiliary derivative state is added as 0.
    assert "__aux_diff_x_1" in m.steady_state
    value = m.steady_state["__aux_diff_x_1"]
    assert isinstance(value, NumberLit) and value.value == 0.0


def test_user_need_not_define_auxiliary_states():
    # x and Y cover the user-declared endogenous; completeness passes
    # without the user mentioning __aux_diff_x_1.
    m = build(parse(HO))
    assert set(m.steady_state) == {"x", "Y", "__aux_diff_x_1"}


# --- duplicate blocks -----------------------------------------------------


def test_multiple_blocks_rejected():
    with pytest.raises(IRError, match="more than one steady_state_model block"):
        ir(COMPLETE + COMPLETE)

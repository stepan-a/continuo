"""Tests for IR construction: the symbol table and declaration validation.

The IR is exercised through the parser (text -> AST -> Model), which is
both the realistic path and the most convenient way to build the ASTs.
"""

from __future__ import annotations

import pytest

from continuo.ir import IRError, build
from continuo.parser import parse
from continuo.parser.ast import VarKind


def ir(src: str):
    return build(parse(src))


# --- symbol table ---------------------------------------------------------


def test_variables_grouped_by_class():
    m = ir("var(state) K, A;\nvar(jump) C, lam;\nvar Y, r, w;")
    assert m.states == ("K", "A")
    assert m.jumps == ("C", "lam")
    assert m.algebraic == ("Y", "r", "w")


def test_var_without_qualifier_is_algebraic():
    m = ir("var Y;")
    assert m.algebraic == ("Y",)
    assert m.states == () and m.jumps == ()


def test_exogenous_and_parameters_collected():
    m = ir("varexo eps, u;\nparameters alpha, beta;")
    assert m.exogenous == ("eps", "u")
    assert m.parameters == ("alpha", "beta")


def test_declaration_order_is_preserved():
    m = ir("var(state) b, a, c;")
    assert m.states == ("b", "a", "c")


def test_endogenous_concatenates_classes_in_order():
    m = ir("var(state) K;\nvar(jump) C;\nvar Y;")
    assert m.endogenous == ("K", "C", "Y")


def test_multiple_declarations_of_same_class_accumulate():
    m = ir("var(state) K;\nvar(state) A;")
    assert m.states == ("K", "A")


# --- kind queries ---------------------------------------------------------


def test_kind_of():
    m = ir("var(state) K;\nvar(jump) C;\nvar Y;")
    assert m.kind_of("K") is VarKind.STATE
    assert m.kind_of("C") is VarKind.JUMP
    assert m.kind_of("Y") is VarKind.ALGEBRAIC
    assert m.kind_of("nope") is None


def test_exogenous_and_parameter_predicates():
    m = ir("var(state) K;\nvarexo eps;\nparameters alpha;")
    assert m.is_exogenous("eps") and not m.is_exogenous("K")
    assert m.is_parameter("alpha") and not m.is_parameter("eps")


# --- parameter values -----------------------------------------------------


def test_parameter_values_recorded():
    m = ir("parameters alpha, beta;\nalpha = 0.33;\nbeta = 0.99;")
    assert set(m.parameter_values) == {"alpha", "beta"}


def test_parameter_value_can_be_an_expression():
    # The value AST is stored unevaluated; only the LHS is validated here.
    m = ir("parameters rho, beta;\nrho = 0.02;\nbeta = 1 / (1 + rho);")
    assert "beta" in m.parameter_values


def test_unset_parameters_have_no_value():
    m = ir("parameters alpha, beta;\nalpha = 0.33;")
    assert "beta" not in m.parameter_values


# --- model block ----------------------------------------------------------


def test_model_equations_collected():
    m = ir("var(state) K;\nvar Y;\nmodel;\n  diff(K) = Y;\n  Y = K;\nend;")
    assert len(m.equations) == 2


def test_no_model_block_is_allowed():
    # A full model will need equations, but building the symbol table does
    # not require them; the "model required" check belongs to a later pass.
    m = ir("var Y;")
    assert m.equations == ()


# --- declaration errors ---------------------------------------------------


def test_duplicate_declaration_rejected():
    with pytest.raises(IRError, match="already declared as state"):
        ir("var(state) K;\nvar(jump) K;")


def test_cross_category_collision_rejected():
    with pytest.raises(IRError, match="already declared"):
        ir("var(state) K;\nvarexo K;")


def test_reserved_prefix_rejected():
    with pytest.raises(IRError, match="reserved"):
        ir("var(state) __aux_x;")


def test_error_carries_position():
    with pytest.raises(IRError) as exc:
        ir("var(state) K;\nvarexo K;")
    assert exc.value.pos is not None
    assert exc.value.pos.line == 2


# --- parameter-value errors -----------------------------------------------


def test_value_for_undeclared_parameter_rejected():
    with pytest.raises(IRError, match="undeclared parameter"):
        ir("alpha = 0.33;")


def test_value_assigned_to_non_parameter_rejected():
    with pytest.raises(IRError, match="only parameters take values"):
        ir("var(state) K;\nK = 1;")


def test_duplicate_parameter_value_rejected():
    with pytest.raises(IRError, match="duplicate value"):
        ir("parameters a;\na = 1;\na = 2;")


# --- model-block errors ---------------------------------------------------


def test_multiple_model_blocks_rejected():
    with pytest.raises(IRError, match="more than one model block"):
        ir("model;\nx = 1;\nend;\nmodel;\ny = 2;\nend;")

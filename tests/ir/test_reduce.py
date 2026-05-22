"""Tests for the higher-order-derivative reduction pass."""

from __future__ import annotations

import pytest

from dynare_ct.ir import IRError, build
from dynare_ct.parser import parse
from dynare_ct.parser.ast import FunctionCall, Identifier


def ir(src: str):
    return build(parse(src))


def assert_all_first_order(model):
    """Every remaining diff call must be diff(<single variable>)."""
    for eq in model.equations:
        calls: list = []
        for side in (eq.lhs, eq.rhs):
            if side is not None:
                _collect(side, calls)
        for call in calls:
            assert len(call.args) == 1, f"non-first-order diff remains: {call}"
            assert isinstance(call.args[0], Identifier)


def _collect(expr, out):
    if isinstance(expr, FunctionCall) and expr.name.name == "diff":
        out.append(expr)
    for value in vars(expr).values():
        if isinstance(value, list):
            for item in value:
                if hasattr(item, "__dict__"):
                    _collect(item, out)
        elif hasattr(value, "__dict__"):
            _collect(value, out)


# --- no-op on first-order models ------------------------------------------


def test_first_order_model_is_unchanged():
    m = ir("var(state) K;\nvar Y;\nmodel;\n  diff(K) = Y;\n  Y = K;\nend;")
    assert m.states == ("K",)
    assert len(m.equations) == 2


# --- second order ---------------------------------------------------------


def test_second_order_introduces_one_auxiliary_state():
    m = ir("var(state) x;\nvar Y;\nmodel;\n  diff(x, 2) = Y;\n  Y = x;\nend;")
    assert m.states == ("x", "__aux_diff_x_1")
    # Two original equations plus one auxiliary defining equation.
    assert len(m.equations) == 3
    assert_all_first_order(m)


def test_third_order_introduces_two_auxiliary_states():
    m = ir("var(state) x;\nvar Y;\nmodel;\n  diff(x, 3) = Y;\n  Y = x;\nend;")
    assert m.states == ("x", "__aux_diff_x_1", "__aux_diff_x_2")
    assert len(m.equations) == 4
    assert_all_first_order(m)


def test_nested_diff_is_equivalent_to_order_two():
    m = ir("var(state) x;\nvar Y;\nmodel;\n  diff(diff(x)) = Y;\n  Y = x;\nend;")
    assert m.states == ("x", "__aux_diff_x_1")
    assert len(m.equations) == 3
    assert_all_first_order(m)


def test_auxiliary_inherits_jump_class():
    m = ir("var(jump) c;\nvar Y;\nmodel;\n  diff(c, 2) = Y;\n  Y = c;\nend;")
    assert m.jumps == ("c", "__aux_diff_c_1")
    assert m.states == ()


def test_higher_order_keeps_system_square():
    m = ir("var(state) x;\nvar Y;\nmodel;\n  diff(x, 3) = Y;\n  Y = x;\nend;")
    assert len(m.equations) == len(m.endogenous)


# --- order 0 and order 1 normalisation ------------------------------------


def test_order_zero_is_identity():
    # diff(B, 0) == B, so B is not differentiated and stays algebraic.
    m = ir("var A, B;\nmodel;\n  A = diff(B, 0);\n  B = A + 1;\nend;")
    assert m.algebraic == ("A", "B")
    assert_all_first_order(m)  # no diff calls remain at all


def test_order_one_argument_is_accepted():
    m = ir("var(state) K;\nvar Y;\nmodel;\n  diff(K, 1) = Y;\n  Y = K;\nend;")
    assert m.states == ("K",)
    assert len(m.equations) == 2


# --- order-argument errors ------------------------------------------------


def test_negative_order_rejected():
    with pytest.raises(IRError, match="non-negative"):
        ir("var(state) K;\nvar Y;\nmodel;\n  diff(K, -1) = Y;\n  Y = K;\nend;")


def test_non_integer_order_rejected():
    with pytest.raises(IRError, match="must be an integer"):
        ir("var(state) K;\nvar Y;\nmodel;\n  diff(K, 2.5) = Y;\n  Y = K;\nend;")


def test_non_literal_order_rejected():
    with pytest.raises(IRError, match="integer literal"):
        ir(
            "var(state) K;\nvar Y;\nparameters n;\nn = 2;\n"
            "model;\n  diff(K, n) = Y;\n  Y = K;\nend;"
        )


def test_too_many_arguments_rejected():
    with pytest.raises(IRError, match="one or two arguments"):
        ir("var(state) K;\nvar Y;\nmodel;\n  diff(K, 2, 3) = Y;\n  Y = K;\nend;")


def test_second_order_of_algebraic_rejected():
    with pytest.raises(IRError, match="non-dynamic variable"):
        ir("var Y;\nvar(state) K;\nmodel;\n  diff(Y, 2) = K;\n  diff(K) = Y;\nend;")

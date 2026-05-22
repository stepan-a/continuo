"""Tests for the macro expression evaluator."""

from __future__ import annotations

import pytest

from continuo.macro.eval import MacroError, evaluate, is_truthy, value_to_text


def ev(text: str, **env):
    return evaluate(text, env)


# --- literals and types ---------------------------------------------------


def test_integer_literal_stays_int():
    assert ev("42") == 42
    assert isinstance(ev("42"), int)


def test_real_literal():
    assert ev("3.14") == pytest.approx(3.14)
    assert isinstance(ev("3.14"), float)
    assert ev("1e3") == pytest.approx(1000.0)


def test_string_literals_both_quotes():
    assert ev('"hi"') == "hi"
    assert ev("'hi'") == "hi"


def test_boolean_literals():
    assert ev("true") is True
    assert ev("TRUE") is True
    assert ev("false") is False


def test_array_literal():
    assert ev("[1, 2, 3]") == [1, 2, 3]
    assert ev('["a", "b"]') == ["a", "b"]
    assert ev("[]") == []


# --- arithmetic -----------------------------------------------------------


def test_arithmetic_precedence():
    assert ev("2 + 3 * 4") == 14
    assert ev("(2 + 3) * 4") == 20


def test_power_is_right_associative():
    assert ev("2 ^ 3 ^ 2") == 512


def test_int_arithmetic_preserves_int():
    assert isinstance(ev("6 / 3"), int)
    assert ev("6 / 3") == 2


def test_division_promotes_to_float_when_inexact():
    assert ev("7 / 2") == pytest.approx(3.5)
    assert isinstance(ev("7 / 2"), float)


def test_unary_minus():
    assert ev("-5") == -5
    assert ev("3 - -2") == 5


def test_division_by_zero_raises():
    with pytest.raises(MacroError, match="division by zero"):
        ev("1 / 0")


# --- comparison and logic -------------------------------------------------


@pytest.mark.parametrize(
    "expr,expected",
    [
        ("1 < 2", True),
        ("2 <= 2", True),
        ("3 > 4", False),
        ("3 == 3", True),
        ("3 != 3", False),
        ('"a" < "b"', True),
        ("true && false", False),
        ("true || false", True),
        ("!false", True),
        ("1 < 2 && 2 < 3", True),
    ],
)
def test_comparison_and_logic(expr, expected):
    assert ev(expr) is expected


def test_logical_and_short_circuits():
    # Right operand would raise if evaluated; && must not evaluate it.
    assert ev("false && (1 / 0 == 0)") is False


def test_comparing_incompatible_types_raises():
    with pytest.raises(MacroError, match="cannot compare"):
        ev('1 < "a"')


# --- ranges, indexing, membership ----------------------------------------


def test_range_is_inclusive():
    assert ev("1:5") == [1, 2, 3, 4, 5]
    assert ev("3:3") == [3]


def test_descending_range_is_empty():
    assert ev("5:1") == []


def test_indexing_is_one_based():
    assert ev("v[1]", v=[10, 20, 30]) == 10
    assert ev("v[3]", v=[10, 20, 30]) == 30


def test_string_indexing():
    assert ev('"abc"[2]') == "b"


def test_index_out_of_range_raises():
    with pytest.raises(MacroError, match="out of range"):
        ev("v[4]", v=[1, 2, 3])


def test_membership():
    assert ev("2 in v", v=[1, 2, 3]) is True
    assert ev("9 in v", v=[1, 2, 3]) is False
    assert ev('"b" in "abc"') is True


# --- concatenation --------------------------------------------------------


def test_string_concatenation():
    assert ev('"K_" + "US"') == "K_US"


def test_list_concatenation():
    assert ev("[1, 2] + [3]") == [1, 2, 3]


# --- builtins -------------------------------------------------------------


def test_length_of_list_and_string():
    assert ev("length(v)", v=[1, 2, 3]) == 3
    assert ev('length("abcd")') == 4


def test_range_builtin_with_step():
    assert ev("range(0, 10, 2)") == [0, 2, 4, 6, 8, 10]


def test_unknown_function_raises():
    with pytest.raises(MacroError, match="unknown macro function"):
        ev("frobnicate(1)")


# --- variables ------------------------------------------------------------


def test_variable_lookup():
    assert ev("alpha + 1", alpha=2) == 3


def test_undefined_variable_raises():
    with pytest.raises(MacroError, match="undefined macro variable 'beta'"):
        ev("beta")


# --- helpers --------------------------------------------------------------


def test_is_truthy():
    assert is_truthy(True) is True
    assert is_truthy(0) is False
    assert is_truthy(2) is True
    with pytest.raises(MacroError):
        is_truthy("nonempty")


def test_value_to_text_rendering():
    assert value_to_text(3) == "3"
    assert value_to_text("EU") == "EU"
    assert value_to_text(True) == "true"
    assert value_to_text([1, 2]) == "1, 2"


# --- syntax errors --------------------------------------------------------


@pytest.mark.parametrize("expr", ["1 +", "(1", "1 2", "@", '"unterminated'])
def test_syntax_errors_raise(expr):
    with pytest.raises(MacroError):
        ev(expr)

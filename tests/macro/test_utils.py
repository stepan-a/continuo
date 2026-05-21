"""Tests for type-predicate and utility builtins."""

from __future__ import annotations

import pytest

from dynare_ct.macro import MacroError, expand_string
from dynare_ct.macro.eval import evaluate


def ev(text: str, **env):
    return evaluate(text, env)


def lines(src: str, **env) -> list[str]:
    text, _ = expand_string(src, env=env or None)
    return text.splitlines()


# --- defined --------------------------------------------------------------


def test_defined_true_and_false():
    assert ev("defined(x)", x=1) is True
    assert ev("defined(y)") is False


def test_defined_does_not_evaluate_its_argument():
    # `y` is undefined; defined() must not raise.
    assert ev("defined(y)") is False


def test_defined_in_condition():
    assert lines("@#define a = 1\n@#if defined(a)\nyes;\n@#endif") == ["yes;"]
    assert lines("@#if !defined(b)\nno_b;\n@#endif") == ["no_b;"]


def test_defined_sees_function_macros():
    src = "@#define f(x) = x\n@#if defined(f)\nyes;\n@#endif"
    assert lines(src) == ["yes;"]


def test_defined_requires_a_bare_name():
    with pytest.raises(MacroError, match="macro variable name"):
        ev('defined("x")')


# --- type predicates ------------------------------------------------------


@pytest.mark.parametrize(
    "expr,expected",
    [
        ("isreal(3)", True),  # integers are reals, as in Dynare
        ("isreal(3.5)", True),
        ("isreal(true)", False),
        ('isreal("a")', False),
        ("isinteger(3)", True),
        ("isinteger(3.5)", False),
        ("isinteger(true)", False),
        ('isstring("a")', True),
        ("isstring(3)", False),
        ("isboolean(true)", True),
        ("isboolean(1)", False),
        ("isarray([1, 2])", True),
        ("isarray((1, 2))", False),
        ("istuple((1, 2))", True),
        ("istuple([1, 2])", False),
    ],
)
def test_type_predicates(expr, expected):
    assert ev(expr) is expected


def test_type_predicate_arity():
    with pytest.raises(MacroError, match="expects 1 argument"):
        ev("isreal(1, 2)")


# --- isempty --------------------------------------------------------------


def test_isempty():
    assert ev("isempty([])") is True
    assert ev("isempty([1])") is False
    assert ev('isempty("")') is True
    assert ev('isempty("a")') is False


def test_isempty_rejects_non_sequence():
    with pytest.raises(MacroError, match="isempty"):
        ev("isempty(3)")


# --- sum ------------------------------------------------------------------


def test_sum_of_ints_stays_int():
    result = ev("sum([1, 2, 3])")
    assert result == 6
    assert isinstance(result, int)


def test_sum_with_float_promotes():
    assert ev("sum([1, 2.5])") == pytest.approx(3.5)


def test_sum_of_empty_is_zero():
    assert ev("sum([])") == 0


def test_sum_of_tuple():
    assert ev("sum((1, 2, 3))") == 6


def test_sum_rejects_non_numeric():
    with pytest.raises(MacroError, match="numeric"):
        ev('sum([1, "a"])')


# --- casting --------------------------------------------------------------


def test_string_cast():
    assert ev("string(3)") == "3"
    assert ev("string(3.5)") == "3.5"
    assert ev("string(true)") == "true"
    assert ev('string("x")') == "x"


def test_real_cast():
    assert ev('real("3.5")') == pytest.approx(3.5)
    assert isinstance(ev("real(3)"), float)


def test_real_cast_failure():
    with pytest.raises(MacroError, match="cannot convert"):
        ev('real("abc")')


def test_real_rejects_boolean():
    with pytest.raises(MacroError, match="boolean"):
        ev("real(true)")


def test_bool_cast():
    assert ev("bool(1)") is True
    assert ev("bool(0)") is False
    assert ev("bool(true)") is True


def test_bool_rejects_string():
    with pytest.raises(MacroError, match="bool"):
        ev('bool("x")')


# --- composition ----------------------------------------------------------


def test_utilities_compose():
    # Keep only the numeric entries of a heterogeneous array, then sum.
    assert ev("sum([x for x in xs if isreal(x)])", xs=[1, "a", 2, True, 3]) == 6

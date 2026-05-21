"""Tests for tuple values and comprehensions in the macro language."""

from __future__ import annotations

import pytest

from dynare_ct.macro import MacroError, expand_string
from dynare_ct.macro.eval import evaluate


def ev(text: str, **env):
    return evaluate(text, env)


def lines(src: str, **env) -> list[str]:
    text, _ = expand_string(src, env=env or None)
    return text.splitlines()


# --- tuple literals -------------------------------------------------------


def test_tuple_literal():
    assert ev("(1, 2, 3)") == (1, 2, 3)


def test_parens_without_comma_are_grouping_not_a_tuple():
    assert ev("(1 + 2) * 3") == 9
    assert ev("(5)") == 5


def test_one_element_tuple_needs_trailing_comma():
    assert ev("(7,)") == (7,)


def test_mixed_type_tuple():
    assert ev('(1, "a", true)') == (1, "a", True)


def test_tuple_indexing_is_one_based():
    assert ev("(10, 20, 30)[2]") == 20


def test_tuple_length_and_membership():
    assert ev("length((1, 2, 3))") == 3
    assert ev("2 in (1, 2, 3)") is True
    assert ev("9 in (1, 2, 3)") is False


def test_tuple_equality():
    assert ev("(1, 2) == (1, 2)") is True
    assert ev("(1, 2) == (1, 3)") is False


def test_tuple_inline_rendering():
    assert lines("x = @{(1, 2)};") == ["x = (1, 2);"]


# --- comprehensions -------------------------------------------------------


def test_basic_comprehension():
    assert ev("[i * i for i in 1:4]") == [1, 4, 9, 16]


def test_comprehension_over_array():
    assert ev('[c for c in ["US", "EU"]]') == ["US", "EU"]


def test_comprehension_with_filter():
    assert ev("[i for i in 1:10 if mod(i, 2) == 0]") == [2, 4, 6, 8, 10]


def test_comprehension_building_tuples():
    assert ev("[(i, i * i) for i in 1:3]") == [(1, 1), (2, 4), (3, 9)]


def test_nested_for_clauses():
    assert ev("[i * j for i in 1:2 for j in 1:2]") == [1, 2, 2, 4]


def test_comprehension_with_tuple_destructuring():
    assert ev("[a + b for (a, b) in pairs]", pairs=[(1, 2), (3, 4)]) == [3, 7]


def test_comprehension_scope_does_not_leak():
    # The comprehension variable must not bind in the surrounding env.
    with pytest.raises(MacroError, match="undefined macro variable 'i'"):
        ev("[i for i in 1:3] + [i]")


def test_empty_comprehension():
    assert ev("[i for i in 1:10 if i > 100]") == []


def test_comprehension_bad_iterable_raises():
    with pytest.raises(MacroError, match="can only iterate"):
        ev("[i for i in 5]")


def test_comprehension_unpack_mismatch_raises():
    with pytest.raises(MacroError, match="cannot unpack"):
        ev("[a + b for (a, b) in items]", items=[(1, 2, 3)])


# --- @#for tuple destructuring --------------------------------------------


def test_for_tuple_destructuring():
    src = "@#define ps = [(1, 2), (3, 4)]\n@#for (a, b) in ps\ne_@{a}_@{b};\n@#endfor"
    assert lines(src) == ["e_1_2;", "e_3_4;"]


def test_for_over_comprehension_of_tuples():
    src = "@#for (i, sq) in [(k, k * k) for k in 1:3]\nx@{i} = @{sq};\n@#endfor"
    assert lines(src) == ["x1 = 1;", "x2 = 4;", "x3 = 9;"]


def test_for_tuple_unpack_mismatch_reports_position():
    src = "ok;\n@#for (a, b) in [(1, 2, 3)]\nx;\n@#endfor"
    with pytest.raises(MacroError) as exc:
        expand_string(src, filename="m.mod")
    assert exc.value.line == 2
    assert "cannot unpack" in str(exc.value)


def test_for_single_var_still_works():
    assert lines("@#for i in 1:2\nr@{i};\n@#endfor") == ["r1;", "r2;"]


def test_for_tuple_target_needs_a_name():
    with pytest.raises(MacroError, match="needs at least one name"):
        expand_string("@#for () in x\ny;\n@#endfor")

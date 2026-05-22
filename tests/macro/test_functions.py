"""Tests for function macros: @#define f(args) = body."""

from __future__ import annotations

import pytest

from continuo.macro import MacroError, expand_string


def expand(src: str, **env) -> str:
    text, _ = expand_string(src, env=env or None)
    return text


def lines(src: str, **env) -> list[str]:
    return expand(src, **env).splitlines()


# --- definition and application -------------------------------------------


def test_single_argument_function():
    assert lines("@#define sq(x) = x^2\ny = @{sq(3)};") == ["y = 9;"]


def test_multiple_argument_function():
    assert lines("@#define add(a, b) = a + b\nz = @{add(2, 5)};") == ["z = 7;"]


def test_zero_argument_function():
    assert lines("@#define answer() = 42\nx = @{answer()};") == ["x = 42;"]


def test_string_building_function():
    assert lines('@#define nm(c) = "K_" + c\nvar @{nm("US")};') == ["var K_US;"]


def test_function_returning_boolean_in_condition():
    src = "@#define big(x) = x > 5\n@#if big(10)\nyes;\n@#endif"
    assert lines(src) == ["yes;"]


def test_function_used_in_for_range():
    src = "@#define n() = 3\n@#for i in 1:n()\ne@{i};\n@#endfor"
    assert lines(src) == ["e1;", "e2;", "e3;"]


# --- composition and scoping ----------------------------------------------


def test_nested_function_calls():
    src = "@#define sq(x) = x^2\n@#define quad(x) = sq(sq(x))\nv = @{quad(2)};"
    assert lines(src) == ["v = 16;"]


def test_free_variables_are_late_bound():
    # `scale` references `factor`, which is defined *after* it; resolution
    # happens at call time, so this must work.
    src = "@#define scale(x) = x * factor\n@#define factor = 10\nr = @{scale(3)};"
    assert lines(src) == ["r = 30;"]


def test_parameter_shadows_outer_variable():
    src = "@#define x = 100\n@#define f(x) = x + 1\nr = @{f(5)};"
    assert lines(src) == ["r = 6;"]


def test_argument_is_evaluated_before_the_call():
    src = "@#define f(x) = x * x\nr = @{f(2 + 1)};"
    assert lines(src) == ["r = 9;"]


# --- errors ---------------------------------------------------------------


def test_wrong_argument_count_raises():
    with pytest.raises(MacroError, match="expects 2 argument"):
        expand("@#define add(a, b) = a + b\nx = @{add(1)};")


def test_calling_a_non_function_raises():
    with pytest.raises(MacroError, match="is not a macro function"):
        expand("@#define x = 3\ny = @{x(1)};")


def test_unknown_function_still_raises():
    with pytest.raises(MacroError, match="unknown macro function"):
        expand("y = @{nope(1)};")


def test_duplicate_parameter_name_raises():
    with pytest.raises(MacroError, match="duplicate parameter name"):
        expand("@#define f(x, x) = x\n")


def test_invalid_parameter_name_raises():
    with pytest.raises(MacroError, match="invalid parameter name"):
        expand("@#define f(1x) = 1\n")


def test_body_syntax_error_reported_at_definition_line():
    src = "ok;\n@#define f(x) = x +\nz = @{f(1)};"
    with pytest.raises(MacroError) as exc:
        expand(src)
    assert exc.value.line == 2  # the @#define line, not the call site

"""Tests for directive expansion and inline @{...} substitution."""

from __future__ import annotations

import pytest

from dynare_ct.macro import MacroError, expand_string


def expand(src: str, **env) -> str:
    text, _ = expand_string(src, env=env or None)
    return text


def lines(src: str, **env) -> list[str]:
    return expand(src, **env).splitlines()


# --- passthrough ----------------------------------------------------------


def test_plain_text_passes_through_unchanged():
    src = "var x;\nmodel;\nx = 1;\nend;"
    assert lines(src) == ["var x;", "model;", "x = 1;", "end;"]


def test_directive_lines_are_consumed():
    # The @#define line must not appear in the output.
    assert lines("@#define a = 1\nfoo;") == ["foo;"]


# --- inline expansion -----------------------------------------------------


def test_inline_scalar_expansion():
    assert lines("@#define a = 0.5\nx = @{a};") == ["x = 0.5;"]


def test_inline_expression_expansion():
    assert lines("@#define n = 3\ny = @{n * n};") == ["y = 9;"]


def test_multiple_expansions_one_line():
    assert lines('@#define c = "US"\nK_@{c} = A_@{c};') == ["K_US = A_US;"]


def test_string_value_expands_without_quotes():
    assert lines('@#define c = "EU"\nvar K_@{c};') == ["var K_EU;"]


# --- @#for ----------------------------------------------------------------


def test_for_over_array():
    src = '@#define cs = ["US", "EU"]\n@#for c in cs\nvar K_@{c};\n@#endfor'
    assert lines(src) == ["var K_US;", "var K_EU;"]


def test_for_over_range():
    src = "@#for i in 1:3\neq@{i};\n@#endfor"
    assert lines(src) == ["eq1;", "eq2;", "eq3;"]


def test_empty_for_produces_nothing():
    assert lines("@#for i in 5:1\nx@{i};\n@#endfor") == []


def test_nested_for():
    src = "@#for i in 1:2\n@#for j in 1:2\nA_@{i}_@{j};\n@#endfor\n@#endfor"
    assert lines(src) == ["A_1_1;", "A_1_2;", "A_2_1;", "A_2_2;"]


def test_for_requires_list():
    with pytest.raises(MacroError, match="can only iterate over a list"):
        expand("@#for i in 3\nx;\n@#endfor")


# --- @#if / @#elseif / @#else --------------------------------------------


def test_if_true_branch():
    assert lines("@#if 1 < 2\nyes;\n@#else\nno;\n@#endif") == ["yes;"]


def test_if_false_branch():
    assert lines("@#if 1 > 2\nyes;\n@#else\nno;\n@#endif") == ["no;"]


def test_if_without_else_and_false():
    assert lines("@#if false\nyes;\n@#endif") == []


def test_elseif_chain():
    src = (
        "@#define k = 2\n"
        "@#if k == 1\na;\n"
        "@#elseif k == 2\nb;\n"
        "@#elseif k == 3\nc;\n"
        "@#else\nd;\n"
        "@#endif"
    )
    assert lines(src) == ["b;"]


def test_define_in_untaken_branch_is_skipped():
    # `x` is only defined in the false branch, so referencing it must fail.
    src = "@#if false\n@#define x = 1\n@#endif\nval = @{x};"
    with pytest.raises(MacroError, match="undefined macro variable 'x'"):
        expand(src)


# --- @#ifdef / @#ifndef ---------------------------------------------------


def test_ifdef_true_when_defined():
    assert lines("@#define a = 1\n@#ifdef a\nyes;\n@#endif") == ["yes;"]


def test_ifdef_false_when_undefined():
    assert lines("@#ifdef a\nyes;\n@#endif") == []


def test_ifndef():
    assert lines("@#ifndef a\nno_a;\n@#endif") == ["no_a;"]


# --- seeded environment ---------------------------------------------------


def test_env_seeds_macro_variables():
    assert lines("x = @{scenario};", scenario="baseline") == ["x = baseline;"]


# --- combined -------------------------------------------------------------


def test_loop_with_conditional_body():
    src = "@#for i in 1:3\n@#if i == 2\nmiddle_@{i};\n@#else\nedge_@{i};\n@#endif\n@#endfor"
    assert lines(src) == ["edge_1;", "middle_2;", "edge_3;"]

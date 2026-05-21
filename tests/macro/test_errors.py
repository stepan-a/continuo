"""Tests for macro error reporting: messages and source positions."""

from __future__ import annotations

import pytest

from dynare_ct.macro import MacroError, expand_string


def expand(src: str):
    return expand_string(src, filename="m.mod")


@pytest.mark.parametrize(
    "src,match",
    [
        ("@#define = 1", "malformed @#define"),
        ("@#define x", "malformed @#define"),
        ("@#define 1x = 1", "malformed @#define"),
        ("@#for i 1:3\nx;\n@#endfor", "malformed @#for"),
        ("@#if true\nx;", "unterminated @#if"),
        ("@#for i in 1:3\nx;", "unterminated @#for"),
        ("@#endif", "without a matching opener"),
        ("@#endfor", "without a matching opener"),
        ("@#else", "without a matching opener"),
        ("@#frobnicate x", "unsupported directive"),
        ("@# define x = 1", None),  # whitespace after @# is tolerated
    ],
)
def test_structural_errors(src, match):
    if match is None:
        expand(src)  # must not raise
        return
    with pytest.raises(MacroError, match=match):
        expand(src)


def test_error_carries_filename_and_line():
    src = "ok;\nok;\n@#define = bad\n"
    with pytest.raises(MacroError) as exc:
        expand(src)
    assert exc.value.file == "m.mod"
    assert exc.value.line == 3
    assert "m.mod:3:" in str(exc.value)


def test_eval_error_inside_inline_reports_line():
    src = "a;\nb;\nx = @{undefined_var};\n"
    with pytest.raises(MacroError) as exc:
        expand(src)
    assert exc.value.line == 3


def test_unterminated_inline_expansion():
    with pytest.raises(MacroError, match="unterminated @"):
        expand("x = @{1 + 2;\n")


def test_if_condition_must_be_boolean_or_numeric():
    with pytest.raises(MacroError, match="condition must be"):
        expand('@#if "string"\nx;\n@#endif')

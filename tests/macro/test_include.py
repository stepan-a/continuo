"""Tests for @#include resolution, nesting, and failure modes."""

from __future__ import annotations

import pytest

from continuo.macro import MacroError, expand, expand_string


def test_basic_include(tmp_path):
    (tmp_path / "params.mod").write_text("alpha = 0.3;\nbeta = 0.99;\n")
    main = tmp_path / "main.mod"
    main.write_text('model;\n@#include "params.mod"\nend;\n')
    text, _ = expand(main)
    assert text.splitlines() == ["model;", "alpha = 0.3;", "beta = 0.99;", "end;"]


def test_include_path_built_from_macro_variable(tmp_path):
    (tmp_path / "params_EU.mod").write_text("alpha = 0.3;\n")
    main = tmp_path / "main.mod"
    main.write_text('@#define region = "EU"\n@#include "params_@{region}.mod"\n')
    text, _ = expand(main)
    assert text.splitlines() == ["alpha = 0.3;"]


def test_included_file_sees_caller_definitions(tmp_path):
    (tmp_path / "use.mod").write_text("x = @{a};\n")
    main = tmp_path / "main.mod"
    main.write_text('@#define a = 7\n@#include "use.mod"\n')
    text, _ = expand(main)
    assert text.splitlines() == ["x = 7;"]


def test_nested_include(tmp_path):
    (tmp_path / "inner.mod").write_text("inner;\n")
    (tmp_path / "outer.mod").write_text('before;\n@#include "inner.mod"\nafter;\n')
    main = tmp_path / "main.mod"
    main.write_text('@#include "outer.mod"\n')
    text, _ = expand(main)
    assert text.splitlines() == ["before;", "inner;", "after;"]


def test_missing_include_raises(tmp_path):
    main = tmp_path / "main.mod"
    main.write_text('@#include "nope.mod"\n')
    with pytest.raises(MacroError, match="file not found"):
        expand(main)


def test_circular_include_raises(tmp_path):
    a = tmp_path / "a.mod"
    b = tmp_path / "b.mod"
    a.write_text('@#include "b.mod"\n')
    b.write_text('@#include "a.mod"\n')
    with pytest.raises(MacroError, match="circular @#include"):
        expand(a)


def test_include_relative_to_string_base_dir(tmp_path):
    (tmp_path / "frag.mod").write_text("frag;\n")
    text, _ = expand_string('@#include "frag.mod"\n', base_dir=tmp_path)
    assert text.splitlines() == ["frag;"]

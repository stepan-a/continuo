"""Tests for the remaining macro features: slicing, set-difference,
diagnostic directives, @#includepath, and directive lexical niceties."""

from __future__ import annotations

import pytest

from continuo.macro import MacroError, expand, expand_string
from continuo.macro.eval import evaluate


def ev(text: str, **env):
    return evaluate(text, env)


def lines(src: str, **env) -> list[str]:
    text, _ = expand_string(src, env=env or None)
    return text.splitlines()


# --- slicing --------------------------------------------------------------


def test_array_slice_with_range():
    assert ev("a[2:4]", a=[10, 20, 30, 40, 50]) == [20, 30, 40]


def test_array_slice_keeps_list_type():
    assert isinstance(ev("a[1:2]", a=[1, 2, 3]), list)


def test_string_slice_stays_string():
    assert ev('"abcdef"[2:4]') == "bcd"


def test_tuple_slice_stays_tuple():
    assert ev("t[1:2]", t=(7, 8, 9)) == (7, 8)


def test_empty_slice():
    assert ev("a[3:1]", a=[1, 2, 3]) == []


def test_arbitrary_gather():
    # Indexing by an explicit list selects exactly those positions.
    assert ev("a[[1, 3]]", a=[10, 20, 30]) == [10, 30]


def test_slice_out_of_range_raises():
    with pytest.raises(MacroError, match="out of range"):
        ev("a[2:5]", a=[1, 2, 3])


def test_single_index_still_works():
    assert ev("a[2]", a=[10, 20, 30]) == 20


# --- array set-difference -------------------------------------------------


def test_array_difference():
    assert ev("[1, 2, 3, 4] - [2, 4]") == [1, 3]


def test_array_difference_removes_all_occurrences():
    assert ev("[1, 2, 2, 3, 2] - [2]") == [1, 3]


def test_array_difference_with_no_overlap():
    assert ev("[1, 2] - [3, 4]") == [1, 2]


def test_array_concatenation_still_works():
    assert ev("[1, 2] + [3]") == [1, 2, 3]


# --- @#echo / @#error -----------------------------------------------------


def test_echo_writes_to_stderr(capsys):
    out = lines('@#define n = 3\n@#echo "n is " + string(n)\nx;')
    assert out == ["x;"]  # echo produces no output text
    captured = capsys.readouterr()
    assert "n is 3" in captured.err


def test_echo_requires_a_message():
    with pytest.raises(MacroError, match="@#echo requires"):
        expand_string("@#echo\n")


def test_error_aborts_with_message():
    with pytest.raises(MacroError, match="halt: bad config") as exc:
        expand_string('ok;\n@#error "halt: bad config"\n', filename="m.mod")
    assert exc.value.line == 2


def test_error_only_fires_on_taken_branch():
    # The @#error is in the untaken branch, so expansion succeeds.
    assert lines('@#if false\n@#error "nope"\n@#endif\nok;') == ["ok;"]


def test_echomacrovars_lists_variables(capsys):
    lines("@#define a = 1\n@#define b = 2\n@#echomacrovars\nx;")
    err = capsys.readouterr().err
    assert "Macro variables:" in err
    assert "a = 1" in err
    assert "b = 2" in err


# --- @#includepath --------------------------------------------------------


def test_includepath_resolves_includes(tmp_path):
    libdir = tmp_path / "lib"
    libdir.mkdir()
    (libdir / "frag.mod").write_text("from_lib;\n")
    main = tmp_path / "main.mod"
    main.write_text('@#includepath "lib"\n@#include "frag.mod"\n')
    text, _ = expand(main)
    assert text.splitlines() == ["from_lib;"]


def test_includepath_falls_back_to_local_first(tmp_path):
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "frag.mod").write_text("from_lib;\n")
    (tmp_path / "frag.mod").write_text("local;\n")
    main = tmp_path / "main.mod"
    main.write_text('@#includepath "lib"\n@#include "frag.mod"\n')
    text, _ = expand(main)
    assert text.splitlines() == ["local;"]  # local dir wins


# --- lexical niceties -----------------------------------------------------


def test_line_comment_in_directive():
    assert lines("@#define a = 1 // a comment\nx = @{a};") == ["x = 1;"]


def test_double_slash_inside_string_is_kept():
    assert lines('@#define u = "http://x"\n@{u};') == ["http://x;"]


def test_backslash_line_continuation():
    src = "@#define cs = [1, \\\n            2, \\\n            3]\n@{length(cs)};"
    assert lines(src) == ["3;"]


def test_continuation_preserves_following_line_numbers():
    src = "@#define a = 1 + \\\n        2\nx = @{a};"
    text, lm = expand_string(src, filename="m.mod")
    assert text.splitlines() == ["x = 3;"]
    # The emitted line is physical line 3 of the source.
    assert lm.origin(1).line == 3


def test_comment_does_not_affect_text_lines():
    # // in model text is left for the parser, not stripped by the macro lexer.
    assert lines("x = 1; // model comment") == ["x = 1; // model comment"]

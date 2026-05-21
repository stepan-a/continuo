"""Tests for the line map: every output line points back to its origin."""

from __future__ import annotations

from dynare_ct.macro import expand, expand_string
from dynare_ct.macro.linemap import Frame, LineMap, Origin


def test_plain_lines_map_one_to_one():
    text, lm = expand_string("a;\nb;\nc;\n", filename="m.mod")
    assert len(lm) == 3
    assert lm.origin(1) == Origin("m.mod", 1)
    assert lm.origin(3) == Origin("m.mod", 3)


def test_loop_body_origins_carry_iteration_context():
    src = "@#for i in 1:2\nrow_@{i};\n@#endfor"
    text, lm = expand_string(src, filename="m.mod")
    # Both output lines come from source line 2 (the loop body).
    assert lm.origin(1).line == 2
    assert lm.origin(2).line == 2
    # ... but with distinct iteration frames.
    assert lm.origin(1).context[-1].detail == "iteration 1"
    assert lm.origin(2).context[-1].detail == "iteration 2"


def test_format_location_for_loop():
    src = "@#for c in [1]\nx_@{c};\n@#endfor"
    _, lm = expand_string(src, filename="m.mod")
    loc = lm.format_location(1)
    assert "m.mod line 2" in loc
    assert "@#for c in [1]" in loc
    assert "iteration 1" in loc


def test_format_location_through_include(tmp_path):
    (tmp_path / "inc.mod").write_text("included;\n")
    main = tmp_path / "main.mod"
    main.write_text('top;\n@#include "inc.mod"\n')
    _, lm = expand(main)
    # Output line 2 is the included content.
    loc = lm.format_location(2)
    assert "inc.mod line 1" in loc
    assert "@#include" in loc
    assert "main.mod" in loc


def test_out_of_range_origin_raises():
    _, lm = expand_string("a;\n")
    try:
        lm.origin(99)
    except IndexError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected IndexError")


def test_linemap_building_blocks():
    lm = LineMap()
    lm.append(Origin("f", 1, (Frame("@#include", "at line 3 of main.mod"),)))
    assert len(lm) == 1
    assert "at line 3 of main.mod" in lm.format_location(1)

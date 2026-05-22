"""Tests for parsing the shocks block, including multi-revelation paths."""

from __future__ import annotations

import pytest

from continuo.parser import parse
from continuo.parser.ast import (
    BinaryOp,
    FunctionCall,
    Identifier,
    NumberLit,
    PathAssignment,
    ShockEntry,
    ShocksBlock,
    UnaryOp,
)
from continuo.parser.errors import LarkError


def _shocks(text: str) -> ShocksBlock:
    """Parse a single shocks block; return the ShocksBlock."""
    stmt = parse(text).statements[0]
    assert isinstance(stmt, ShocksBlock)
    return stmt


# --- structure -----------------------------------------------------------


def test_empty_shocks_block():
    sb = _shocks("shocks; end;")
    assert sb.entries == []


def test_single_shock_default_path():
    sb = _shocks(
        """
        shocks;
          var z;
          path = 0.02;
        end;
        """
    )
    assert len(sb.entries) == 1
    entry = sb.entries[0]
    assert isinstance(entry, ShockEntry)
    assert entry.name.name == "z"
    assert len(entry.paths) == 1
    p = entry.paths[0]
    assert isinstance(p, PathAssignment)
    assert p.reveal_time is None
    assert isinstance(p.path, NumberLit) and p.path.value == 0.02


def test_single_shock_path_at_t0():
    sb = _shocks(
        """
        shocks;
          var z;
          path at t=0 = 0.05;
        end;
        """
    )
    p = sb.entries[0].paths[0]
    assert isinstance(p.reveal_time, NumberLit) and p.reveal_time.value == 0.0
    assert isinstance(p.path, NumberLit) and p.path.value == 0.05


def test_multi_revelation_paths():
    """The MIT-shock idiom: multiple (reveal_time, path) pairs per shock."""
    sb = _shocks(
        """
        shocks;
          var u;
          path at t=0  = 0.05;
          path at t=5  = 0.06;
          path at t=10 = 0.025;
        end;
        """
    )
    paths = sb.entries[0].paths
    assert len(paths) == 3
    times = [p.reveal_time.value for p in paths]
    values = [p.path.value for p in paths]
    assert times == [0.0, 5.0, 10.0]
    assert values == [0.05, 0.06, 0.025]


def test_multiple_shocks():
    sb = _shocks(
        """
        shocks;
          var A;
          path = 1.0;

          var delta;
          path at t=0 = 0.05;
          path at t=5 = 0.06;
        end;
        """
    )
    assert len(sb.entries) == 2
    assert sb.entries[0].name.name == "A"
    assert len(sb.entries[0].paths) == 1
    assert sb.entries[1].name.name == "delta"
    assert len(sb.entries[1].paths) == 2


def test_path_with_if_expression():
    """Anticipated change: single belief, conditional path."""
    sb = _shocks(
        """
        shocks;
          var delta;
          path = if(t < 5, 0.05, 0.06);
        end;
        """
    )
    p = sb.entries[0].paths[0]
    assert p.reveal_time is None
    assert isinstance(p.path, FunctionCall)
    assert p.path.name.name == "if"
    assert len(p.path.args) == 3


def test_path_with_helper_call():
    """The pulse helper exposes its discontinuities through positional args."""
    sb = _shocks(
        """
        shocks;
          var A;
          path = 1.0 + 0.05 * pulse(t, 8, 12);
        end;
        """
    )
    p = sb.entries[0].paths[0]
    assert isinstance(p.path, BinaryOp) and p.path.op == "+"
    # Right side is 0.05 * pulse(t, 8, 12).
    assert isinstance(p.path.right, BinaryOp)
    assert isinstance(p.path.right.right, FunctionCall)
    assert p.path.right.right.name.name == "pulse"


def test_path_with_smooth_decay():
    """A surprise that fades — combines reveal time with smooth helper."""
    sb = _shocks(
        """
        shocks;
          var A;
          path at t=0 = 1.0;
          path at t=5 = 1.0 + 0.05 * expdecay(t, 5, 3);
        end;
        """
    )
    paths = sb.entries[0].paths
    assert len(paths) == 2
    # Second path uses expdecay(t, 5, 3).
    second = paths[1].path
    assert isinstance(second, BinaryOp) and second.op == "+"
    decay = second.right.right
    assert isinstance(decay, FunctionCall)
    assert decay.name.name == "expdecay"


def test_reveal_time_can_be_an_identifier():
    """Reveal times are parsed as expressions; an identifier (e.g. a parameter)
    is syntactically valid. The IR validates it is a numeric constant."""
    sb = _shocks(
        """
        shocks;
          var u;
          path at t=t_announce = 0.03;
        end;
        """
    )
    p = sb.entries[0].paths[0]
    assert isinstance(p.reveal_time, Identifier)
    assert p.reveal_time.name == "t_announce"


def test_negative_path_value():
    sb = _shocks(
        """
        shocks;
          var z;
          path = -0.02;
        end;
        """
    )
    p = sb.entries[0].paths[0]
    assert isinstance(p.path, UnaryOp) and p.path.op == "-"


# --- gallery integration -------------------------------------------------


def test_full_unanticipated_permanent_change_example():
    """Example 2 from the design's worked-examples gallery."""
    text = """
    var(state) K;
    var(jump)  C;
    var Y, r;

    varexo A, delta;

    parameters alpha, rho, sigma;
    alpha = 0.33;
    rho   = 0.04;
    sigma = 1.00;

    model;
      Y = A * K^alpha;
      r = alpha * Y / K - delta;
      diff(K) = Y - C - delta * K;
      diff(C) = (r - rho) * C / sigma;
    end;

    steady_state_model_placeholder = 1;

    shocks;
      var A;     path = 1.0;
      var delta;
      path at t=0 = 0.05;
      path at t=5 = 0.06;
    end;

    initval(steady);
    end;
    """
    # NB: steady_state_model is step 6 — it's not parsed yet, hence the
    # placeholder above. This test confirms a near-complete .mod file
    # with a multi-revelation shock parses end-to-end.
    model = parse(text)
    sb = next(s for s in model.statements if isinstance(s, ShocksBlock))
    assert len(sb.entries) == 2
    delta_entry = next(e for e in sb.entries if e.name.name == "delta")
    assert len(delta_entry.paths) == 2
    times = [p.reveal_time.value for p in delta_entry.paths]
    assert times == [0.0, 5.0]


# --- error cases ----------------------------------------------------------


def test_shocks_missing_end_raises():
    with pytest.raises(LarkError):
        parse("shocks; var z; path = 0.02;")


def test_shocks_missing_var_keyword_raises():
    # Without a `var X;` to introduce a shock entry, lone path
    # assignments are rejected.
    with pytest.raises(LarkError):
        parse(
            """
            shocks;
              path = 0.02;
            end;
            """
        )


def test_shock_entry_without_path_raises():
    # A `var X;` must be followed by at least one path assignment
    # (the grammar uses `+` rather than `*`).
    with pytest.raises(LarkError):
        parse(
            """
            shocks;
              var z;
              var u;
              path = 0.05;
            end;
            """
        )


def test_path_assignment_missing_semicolon_raises():
    with pytest.raises(LarkError):
        parse(
            """
            shocks;
              var z;
              path = 0.02
            end;
            """
        )


def test_path_at_with_wrong_time_var_raises():
    # `path at <ident> = …` parses only when <ident> is exactly 't'.
    with pytest.raises(SyntaxError, match=r"expected 't' after 'path at'"):
        parse(
            """
            shocks;
              var u;
              path at s=4 = 0.06;
            end;
            """
        )


def test_path_at_missing_second_equals_raises():
    with pytest.raises(LarkError):
        parse(
            """
            shocks;
              var u;
              path at t=4 0.06;
            end;
            """
        )

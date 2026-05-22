"""Tests for the shocks pass: varexo validation and revelation structure."""

from __future__ import annotations

import pytest

from continuo.ir import IRError, build
from continuo.parser import parse
from continuo.parser.ast import NumberLit

HEADER = """
var(state) K;
var Y;
varexo eps, u;
parameters alpha;
alpha = 0.33;
model;
  diff(K) = Y - K + eps + u;
  Y = K^alpha;
end;
"""


def ir(extra: str = ""):
    return build(parse(HEADER + extra))


def reveal_values(shock):
    return [p.reveal_time.value for p in shock.paths]


# --- collection -----------------------------------------------------------


def test_absent_block_leaves_shocks_empty():
    assert ir().shocks == ()


def test_bare_path_normalises_to_t0():
    m = ir("shocks;\n  var u;\n  path = 0.01;\nend;")
    (shock,) = m.shocks
    assert shock.name == "u"
    assert len(shock.paths) == 1
    assert isinstance(shock.paths[0].reveal_time, NumberLit)
    assert shock.paths[0].reveal_time.value == 0.0


def test_beliefs_sorted_by_reveal_time():
    block = (
        "shocks;\n  var u;\n"
        "  path at t=10 = 0.02;\n  path at t=0 = 0.01;\n  path at t=4 = 0.03;\nend;"
    )
    (shock,) = ir(block).shocks
    assert reveal_values(shock) == [0.0, 4.0, 10.0]


def test_multiple_shocks_collected():
    block = "shocks;\n  var u;\n  path = 0.01;\n  var eps;\n  path = 0.5;\nend;"
    m = ir(block)
    assert {s.name for s in m.shocks} == {"u", "eps"}


# --- name validation ------------------------------------------------------


def test_shock_on_endogenous_rejected():
    with pytest.raises(IRError, match="'K' is endogenous"):
        ir("shocks;\n  var K;\n  path = 1;\nend;")


def test_shock_on_parameter_rejected():
    with pytest.raises(IRError, match="'alpha' is a parameter"):
        ir("shocks;\n  var alpha;\n  path = 1;\nend;")


def test_shock_on_undeclared_rejected():
    with pytest.raises(IRError, match="undeclared variable 'z'"):
        ir("shocks;\n  var z;\n  path = 1;\nend;")


def test_duplicate_shock_entry_rejected():
    block = "shocks;\n  var u;\n  path = 1;\n  var u;\n  path = 2;\nend;"
    with pytest.raises(IRError, match="duplicate shocks entry for 'u'"):
        ir(block)


# --- reveal-time rules ----------------------------------------------------


def test_mixing_bare_and_explicit_t0_rejected():
    block = "shocks;\n  var u;\n  path = 0.01;\n  path at t=0 = 0.02;\nend;"
    with pytest.raises(IRError, match="mixing 'path = "):
        ir(block)


def test_duplicate_reveal_time_rejected():
    block = "shocks;\n  var u;\n  path at t=4 = 0.01;\n  path at t=4 = 0.02;\nend;"
    with pytest.raises(IRError, match="duplicate path at t=4"):
        ir(block)


def test_two_bare_paths_rejected():
    block = "shocks;\n  var u;\n  path = 0.01;\n  path = 0.02;\nend;"
    with pytest.raises(IRError, match="duplicate path at t=0"):
        ir(block)


# --- parametric reveal times ----------------------------------------------


def test_parametric_reveal_time_flows_through():
    # t=t_star is not a literal; it passes through unsorted, no numeric dedup.
    block = (
        "parameters t_star;\n  t_star = 4;\n"
        "shocks;\n  var u;\n  path = 0.01;\n  path at t=t_star = 0.03;\nend;"
    )
    (shock,) = ir(block).shocks
    assert len(shock.paths) == 2


# --- duplicate blocks -----------------------------------------------------


def test_multiple_shocks_blocks_rejected():
    block = "shocks;\n  var u;\n  path = 1;\nend;\nshocks;\n  var eps;\n  path = 1;\nend;"
    with pytest.raises(IRError, match="more than one shocks block"):
        ir(block)

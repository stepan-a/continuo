"""Tests for the domain-constraint validation pass (attach_constraints).

The pass records ``Model.constraints`` (name -> Bound) and validates,
eagerly at build time, that every identifier a bound names is a declared
parameter or exogenous variable — never an endogenous variable, never
undeclared. Two numeric-literal bounds are checked for ``lower < upper``.
"""

from __future__ import annotations

import pytest

from continuo.ir import Bound, IRError, build
from continuo.parser import parse
from continuo.parser.ast import Identifier, NumberLit

# Two states (K, A), one jump (C), one algebraic (Y); a parameter `kmax`
# and an exogenous `eps` are available to name in bounds.
HEADER = """
var(state) K, A;
var(jump) C;
var Y;
varexo eps;
parameters alpha, delta, kmax;
alpha = 0.33;
delta = 0.025;
kmax = 10;
model;
  diff(K) = Y - C;
  diff(A) = eps - A;
  diff(C) = C * (Y - alpha);
  Y = K^alpha + A;
end;
"""

# A complete analytical steady state, so the numerical path never runs.
ANALYTICAL = """
steady_state_model;
  K = (alpha / delta)^(1 / (1 - alpha));
  A = eps;
  Y = K^alpha + A;
  C = Y - delta * K;
end;
"""


# --- collection -----------------------------------------------------------


def test_no_constraints_leaves_dict_empty():
    assert build(parse(HEADER)).constraints == {}


def test_positive_recorded_as_lower_zero():
    m = build(parse(HEADER.replace("var(state) K, A;", "var(state, positive) K, A;")))
    assert m.constraints["K"] == Bound(lower=NumberLit(0.0), upper=None)
    assert m.constraints["A"] == Bound(lower=NumberLit(0.0), upper=None)


def test_negative_recorded_as_upper_zero():
    m = build(parse(HEADER.replace("var(jump) C;", "var(jump, negative) C;")))
    assert m.constraints["C"] == Bound(lower=None, upper=NumberLit(0.0))


def test_boundaries_parameter_bound_recorded():
    m = build(parse(HEADER.replace("var Y;", "var(boundaries=(0, kmax)) Y;")))
    bound = m.constraints["Y"]
    assert isinstance(bound.lower, NumberLit) and bound.lower.value == 0.0
    assert isinstance(bound.upper, Identifier) and bound.upper.name == "kmax"


def test_boundaries_inf_side_open():
    m = build(parse(HEADER.replace("var Y;", "var(boundaries=(kmax, inf)) Y;")))
    bound = m.constraints["Y"]
    assert isinstance(bound.lower, Identifier) and bound.lower.name == "kmax"
    assert bound.upper is None


def test_exogenous_bound_is_allowed():
    m = build(parse(HEADER.replace("var Y;", "var(boundaries=(0, eps)) Y;")))
    assert m.constraints["Y"].upper.name == "eps"


# --- invalid: name validation ---------------------------------------------


def test_endogenous_bound_rejected():
    with pytest.raises(IRError, match="endogenous variable 'K'"):
        build(parse(HEADER.replace("var Y;", "var(boundaries=(0, K)) Y;")))


def test_undeclared_bound_rejected():
    with pytest.raises(IRError, match="undeclared name 'nope'"):
        build(parse(HEADER.replace("var Y;", "var(boundaries=(0, nope)) Y;")))


def test_undeclared_bound_rejected_even_with_analytical_steady_state():
    # The key point: with an analytical steady_state_model the numerical
    # path (and thus bound evaluation) never runs, yet the build still
    # catches a typo in a bound name.
    src = HEADER.replace("var Y;", "var(boundaries=(0, nope)) Y;") + ANALYTICAL
    with pytest.raises(IRError, match="undeclared name 'nope'"):
        build(parse(src))


def test_expression_bound_validated():
    with pytest.raises(IRError, match="undeclared name 'oops'"):
        build(parse(HEADER.replace("var Y;", "var(boundaries=(0, 2 * oops)) Y;")))


# --- invalid: empty domain ------------------------------------------------


def test_empty_domain_literals_rejected():
    with pytest.raises(IRError, match="empty domain"):
        build(parse(HEADER.replace("var Y;", "var(boundaries=(5, 1)) Y;")))


def test_equal_literal_bounds_rejected():
    with pytest.raises(IRError, match="empty domain"):
        build(parse(HEADER.replace("var Y;", "var(boundaries=(1, 1)) Y;")))


def test_negated_literal_order_checked():
    with pytest.raises(IRError, match="empty domain"):
        build(parse(HEADER.replace("var Y;", "var(boundaries=(1, -1)) Y;")))

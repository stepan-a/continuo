"""Tests for parsing the domain-constraint var qualifier.

The qualifier combines an optional type (state/jump) with at most one
domain constraint (positive / negative / boundaries=(lo, hi)). The parser
normalises every constraint to a ``(lower, upper)`` pair of bound
expressions, with a ``None`` side for an open direction.
"""

from __future__ import annotations

import pytest

from continuo.parser import parse
from continuo.parser.ast import (
    Identifier,
    NumberLit,
    UnaryOp,
    VarDecl,
    VarKind,
)


def _decl(text: str) -> VarDecl:
    decl = parse(text).statements[0]
    assert isinstance(decl, VarDecl)
    return decl


# --- valid: positive / negative -------------------------------------------


def test_positive_normalises_to_zero_lower():
    decl = _decl("var(positive) K;")
    assert decl.kind is VarKind.ALGEBRAIC
    lower, upper = decl.constraint
    assert isinstance(lower, NumberLit) and lower.value == 0.0
    assert upper is None


def test_negative_normalises_to_zero_upper():
    decl = _decl("var(negative) X;")
    lower, upper = decl.constraint
    assert lower is None
    assert isinstance(upper, NumberLit) and upper.value == 0.0


def test_type_and_constraint_combine():
    decl = _decl("var(state, positive) K;")
    assert decl.kind is VarKind.STATE
    lower, upper = decl.constraint
    assert isinstance(lower, NumberLit) and lower.value == 0.0
    assert upper is None


def test_order_of_type_and_constraint_is_free():
    decl = _decl("var(positive, jump) C;")
    assert decl.kind is VarKind.JUMP
    assert decl.constraint[0].value == 0.0


# --- valid: boundaries ----------------------------------------------------


def test_boundaries_two_literals():
    decl = _decl("var(boundaries=(0, 1)) u;")
    lower, upper = decl.constraint
    assert lower.value == 0.0 and upper.value == 1.0


def test_boundaries_parameter_upper():
    decl = _decl("var(state, boundaries=(0, kmax)) L;")
    assert decl.kind is VarKind.STATE
    lower, upper = decl.constraint
    assert isinstance(lower, NumberLit) and lower.value == 0.0
    assert isinstance(upper, Identifier) and upper.name == "kmax"


def test_boundaries_inf_upper_is_open():
    decl = _decl("var(boundaries=(kmin, inf)) M;")
    lower, upper = decl.constraint
    assert isinstance(lower, Identifier) and lower.name == "kmin"
    assert upper is None


def test_boundaries_neg_inf_lower_is_open():
    decl = _decl("var(boundaries=(-inf, 0)) W;")
    lower, upper = decl.constraint
    assert lower is None
    assert isinstance(upper, NumberLit) and upper.value == 0.0


def test_boundaries_negative_literal():
    decl = _decl("var(boundaries=(-1, 1)) z;")
    lower, upper = decl.constraint
    assert isinstance(lower, UnaryOp) and lower.op == "-"
    assert upper.value == 1.0


def test_boundaries_expression_bound():
    decl = _decl("var(boundaries=(0, 2 * kmax)) L;")
    _, upper = decl.constraint
    assert upper.op == "*"


# --- valid: unconstrained still works -------------------------------------


def test_plain_state_has_no_constraint():
    decl = _decl("var(state) K;")
    assert decl.kind is VarKind.STATE
    assert decl.constraint is None


def test_unqualified_has_no_constraint():
    decl = _decl("var Y;")
    assert decl.kind is VarKind.ALGEBRAIC
    assert decl.constraint is None


def test_constraint_applies_to_every_name_in_decl():
    decl = _decl("var(positive) K, L, M;")
    assert [n.name for n in decl.names] == ["K", "L", "M"]
    assert decl.constraint[0].value == 0.0


# --- invalid: conflicting qualifiers --------------------------------------


def test_two_types_rejected():
    with pytest.raises(SyntaxError, match="conflicting var type"):
        parse("var(state, jump) K;")


def test_two_constraints_rejected():
    with pytest.raises(SyntaxError, match="more than one domain constraint"):
        parse("var(positive, negative) K;")


def test_constraint_and_boundaries_rejected():
    with pytest.raises(SyntaxError, match="more than one domain constraint"):
        parse("var(positive, boundaries=(0, 1)) K;")


def test_unknown_flag_rejected():
    with pytest.raises(SyntaxError, match="unknown var qualifier"):
        parse("var(strictlypositive) K;")

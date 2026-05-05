"""Tests for the expression sub-grammar.

Expressions are exercised here via parameter-value assignments
(``name = expr;``), the only context in which expressions currently
appear. The same expression grammar is reused inside equation
LHS/RHS once the model block lands.
"""

from __future__ import annotations

import pytest

from dynare_ct.parser import parse
from dynare_ct.parser.ast import (
    BinaryOp,
    Expr,
    FunctionCall,
    Identifier,
    NumberLit,
    ParameterValue,
    UnaryOp,
)
from dynare_ct.parser.errors import LarkError


def _rhs(text: str) -> Expr:
    """Parse a single ``x = <expr>;`` and return the RHS AST node."""
    model = parse(f"x = {text};")
    stmt = model.statements[0]
    assert isinstance(stmt, ParameterValue)
    return stmt.value


# --- atoms ----------------------------------------------------------------


def test_atom_number():
    e = _rhs("3.14")
    assert isinstance(e, NumberLit)
    assert e.value == pytest.approx(3.14)


def test_atom_identifier():
    e = _rhs("alpha")
    assert isinstance(e, Identifier)
    assert e.name == "alpha"


def test_atom_parenthesised():
    # Parentheses must be transparent — the AST should be just NumberLit(1.0).
    e = _rhs("(((1.0)))")
    assert isinstance(e, NumberLit)
    assert e.value == 1.0


# --- unary operators ------------------------------------------------------


def test_unary_minus():
    e = _rhs("-x")
    assert isinstance(e, UnaryOp)
    assert e.op == "-"
    assert isinstance(e.operand, Identifier)
    assert e.operand.name == "x"


def test_unary_minus_on_number():
    e = _rhs("-0.04")
    assert isinstance(e, UnaryOp)
    assert e.op == "-"
    assert isinstance(e.operand, NumberLit)
    assert e.operand.value == pytest.approx(0.04)


def test_unary_not():
    e = _rhs("!flag")
    assert isinstance(e, UnaryOp)
    assert e.op == "!"


def test_double_unary_minus():
    e = _rhs("--x")
    assert isinstance(e, UnaryOp) and e.op == "-"
    assert isinstance(e.operand, UnaryOp) and e.operand.op == "-"


# --- binary arithmetic ----------------------------------------------------


@pytest.mark.parametrize("op", ["+", "-", "*", "/"])
def test_binary_arithmetic(op):
    e = _rhs(f"a {op} b")
    assert isinstance(e, BinaryOp)
    assert e.op == op
    assert isinstance(e.left, Identifier) and e.left.name == "a"
    assert isinstance(e.right, Identifier) and e.right.name == "b"


def test_pow_is_right_associative():
    # a^b^c parses as a^(b^c)
    e = _rhs("a^b^c")
    assert isinstance(e, BinaryOp) and e.op == "^"
    assert isinstance(e.left, Identifier) and e.left.name == "a"
    assert isinstance(e.right, BinaryOp) and e.right.op == "^"
    assert e.right.left.name == "b"
    assert e.right.right.name == "c"


@pytest.mark.parametrize("op", ["+", "-"])
def test_additive_left_associative(op):
    # a OP b OP c parses as (a OP b) OP c
    e = _rhs(f"a {op} b {op} c")
    assert isinstance(e, BinaryOp) and e.op == op
    assert isinstance(e.left, BinaryOp) and e.left.op == op
    assert e.left.left.name == "a"
    assert e.left.right.name == "b"
    assert e.right.name == "c"


@pytest.mark.parametrize("op", ["*", "/"])
def test_multiplicative_left_associative(op):
    e = _rhs(f"a {op} b {op} c")
    assert isinstance(e, BinaryOp) and e.op == op
    assert isinstance(e.left, BinaryOp) and e.left.op == op


# --- precedence -----------------------------------------------------------


def test_mul_binds_tighter_than_add():
    # a + b * c parses as a + (b * c)
    e = _rhs("a + b * c")
    assert isinstance(e, BinaryOp) and e.op == "+"
    assert isinstance(e.left, Identifier) and e.left.name == "a"
    assert isinstance(e.right, BinaryOp) and e.right.op == "*"
    assert e.right.left.name == "b"
    assert e.right.right.name == "c"


def test_pow_binds_tighter_than_mul():
    # a * b ^ c parses as a * (b ^ c)
    e = _rhs("a * b ^ c")
    assert isinstance(e, BinaryOp) and e.op == "*"
    assert isinstance(e.right, BinaryOp) and e.right.op == "^"


def test_unary_minus_binds_tighter_than_mul_but_looser_than_pow():
    # -2^2 parses as -(2^2), not (-2)^2
    e = _rhs("-2^2")
    assert isinstance(e, UnaryOp) and e.op == "-"
    assert isinstance(e.operand, BinaryOp) and e.operand.op == "^"
    assert e.operand.left.value == 2.0
    assert e.operand.right.value == 2.0


def test_parentheses_override_precedence():
    # (a + b) * c parses as (a + b) * c
    e = _rhs("(a + b) * c")
    assert isinstance(e, BinaryOp) and e.op == "*"
    assert isinstance(e.left, BinaryOp) and e.left.op == "+"
    assert e.right.name == "c"


def test_full_precedence_chain():
    # a || b && c == d + e * f ^ -g
    # Expected grouping (low → high): || at top, then &&, then ==, then +,
    # then *, then ^, then unary -.
    e = _rhs("a || b && c == d + e * f ^ -g")
    assert isinstance(e, BinaryOp) and e.op == "||"
    rhs = e.right
    assert isinstance(rhs, BinaryOp) and rhs.op == "&&"
    cmp = rhs.right
    assert isinstance(cmp, BinaryOp) and cmp.op == "=="
    add = cmp.right
    assert isinstance(add, BinaryOp) and add.op == "+"
    mul = add.right
    assert isinstance(mul, BinaryOp) and mul.op == "*"
    pow_ = mul.right
    assert isinstance(pow_, BinaryOp) and pow_.op == "^"
    assert isinstance(pow_.right, UnaryOp) and pow_.right.op == "-"


# --- comparison and logical -----------------------------------------------


@pytest.mark.parametrize("op", ["<", "<=", ">", ">=", "==", "!="])
def test_comparison_operators(op):
    e = _rhs(f"a {op} b")
    assert isinstance(e, BinaryOp)
    assert e.op == op


def test_logical_and():
    e = _rhs("a && b")
    assert isinstance(e, BinaryOp) and e.op == "&&"


def test_logical_or():
    e = _rhs("a || b")
    assert isinstance(e, BinaryOp) and e.op == "||"


def test_and_binds_tighter_than_or():
    # a || b && c parses as a || (b && c)
    e = _rhs("a || b && c")
    assert isinstance(e, BinaryOp) and e.op == "||"
    assert isinstance(e.right, BinaryOp) and e.right.op == "&&"


# --- function calls -------------------------------------------------------


def test_function_call_no_args():
    e = _rhs("now()")
    assert isinstance(e, FunctionCall)
    assert e.name.name == "now"
    assert e.args == []


def test_function_call_one_arg():
    e = _rhs("exp(x)")
    assert isinstance(e, FunctionCall)
    assert e.name.name == "exp"
    assert len(e.args) == 1
    assert isinstance(e.args[0], Identifier) and e.args[0].name == "x"


def test_function_call_many_args():
    e = _rhs("if(t < 5, 0.0, 0.02)")
    assert isinstance(e, FunctionCall)
    assert e.name.name == "if"
    assert len(e.args) == 3
    assert isinstance(e.args[0], BinaryOp) and e.args[0].op == "<"
    assert isinstance(e.args[1], NumberLit)
    assert isinstance(e.args[2], NumberLit)


def test_function_call_nested():
    e = _rhs("exp(log(x))")
    assert isinstance(e, FunctionCall) and e.name.name == "exp"
    inner = e.args[0]
    assert isinstance(inner, FunctionCall) and inner.name.name == "log"
    assert isinstance(inner.args[0], Identifier)


def test_function_call_with_complex_args():
    e = _rhs("f(a + b, c * d, -x)")
    assert isinstance(e, FunctionCall)
    assert len(e.args) == 3
    assert isinstance(e.args[0], BinaryOp) and e.args[0].op == "+"
    assert isinstance(e.args[1], BinaryOp) and e.args[1].op == "*"
    assert isinstance(e.args[2], UnaryOp) and e.args[2].op == "-"


# --- expressions in parameter assignments ---------------------------------


def test_param_value_with_expression():
    pv = parse("alpha = 0.99 / (1 + rho);").statements[0]
    assert isinstance(pv, ParameterValue)
    assert pv.name.name == "alpha"
    assert isinstance(pv.value, BinaryOp) and pv.value.op == "/"


def test_param_value_function_call():
    pv = parse("z = exp(-rho * t);").statements[0]
    assert isinstance(pv.value, FunctionCall)
    assert pv.value.name.name == "exp"


def test_param_value_negative_literal():
    # Was previously rejected; now parses as UnaryOp("-", NumberLit(0.04)).
    pv = parse("rho = -0.04;").statements[0]
    assert isinstance(pv.value, UnaryOp) and pv.value.op == "-"
    assert isinstance(pv.value.operand, NumberLit)
    assert pv.value.operand.value == pytest.approx(0.04)


# --- source positions in expressions --------------------------------------


def test_position_tracked_through_binop():
    # The leading 'a' is at column 5 (after "x = "); the trailing 'c' is later.
    e = _rhs("a + b + c")
    assert isinstance(e, BinaryOp)
    # Walk down to the deepest left-leaf — that's 'a'.
    leftmost = e
    while isinstance(leftmost, BinaryOp):
        leftmost = leftmost.left
    assert isinstance(leftmost, Identifier)
    assert leftmost.pos is not None
    assert leftmost.pos.line == 1


# --- error cases ----------------------------------------------------------


def test_unbalanced_parens_raises():
    with pytest.raises(LarkError):
        parse("x = (a + b;")


def test_missing_operand_raises():
    with pytest.raises(LarkError):
        parse("x = a + ;")


def test_function_call_unclosed_raises():
    with pytest.raises(LarkError):
        parse("x = f(a, b ;")


def test_double_binary_operator_raises():
    with pytest.raises(LarkError):
        parse("x = a ** b;")

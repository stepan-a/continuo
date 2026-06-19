"""Shared expression helpers for the IR passes.

A small set of operations on parsed expressions reused across several passes:
folding a numeric literal to a float, and walking the sub-expression tree.
Keeping them here avoids the per-pass copies these used to have.
"""

from __future__ import annotations

from collections.abc import Iterator

from continuo.parser.ast import BinaryOp, DictLiteral, Expr, FunctionCall, NumberLit, UnaryOp

__all__ = ["numeric_literal", "children", "walk"]


def numeric_literal(expr: Expr | None) -> float | None:
    """The value of a numeric literal (optionally negated), or ``None`` otherwise."""
    if isinstance(expr, NumberLit):
        return expr.value
    if isinstance(expr, UnaryOp) and expr.op == "-" and isinstance(expr.operand, NumberLit):
        return -expr.operand.value
    return None


def children(expr: Expr) -> Iterator[Expr]:
    """Yield the immediate sub-expressions of ``expr``.

    A function call's *name* is not a sub-expression — only its arguments and
    keyword-argument values are — so identifiers collected from a walk are the
    value-position ones, never call names.
    """
    if isinstance(expr, UnaryOp):
        yield expr.operand
    elif isinstance(expr, BinaryOp):
        yield expr.left
        yield expr.right
    elif isinstance(expr, FunctionCall):
        yield from expr.args
        for kw in expr.kwargs:
            yield kw.value
    elif isinstance(expr, DictLiteral):
        for entry in expr.entries:
            yield entry.value


def walk(expr: Expr) -> Iterator[Expr]:
    """Yield ``expr`` and every sub-expression, in pre-order."""
    yield expr
    for child in children(expr):
        yield from walk(child)

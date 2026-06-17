"""Strict domain constraints: validating ``var`` bound qualifiers.

A ``var`` qualifier may carry a domain constraint — ``positive`` (``> 0``),
``negative`` (``< 0``), or ``boundaries=(lo, hi)`` for an explicit open
interval (a ``None`` side is unbounded). The parser normalises every form
to a ``(lower, upper)`` pair of bound expressions; this pass records them
as :class:`~continuo.ir.model.Bound` objects on ``Model.constraints``.

The bound expressions are evaluated only at solve time, so this pass does
the *name* validation eagerly: every identifier a bound names must be a
declared parameter or exogenous variable — never an endogenous variable
(rejected) and never undeclared (rejected). This matters because with an
analytical ``steady_state_model`` the numerical path (and thus bound
evaluation) never runs, so a typo in a bound would otherwise pass
silently; validating at build catches it on every path. Two numeric
literal bounds are additionally checked for ``lower < upper``.
"""

from __future__ import annotations

from dataclasses import replace

from continuo.ir.errors import IRError
from continuo.ir.model import Bound, Model
from continuo.parser.ast import (
    BinaryOp,
    Expr,
    FunctionCall,
    Identifier,
    ModelFile,
    NumberLit,
    UnaryOp,
    VarDecl,
)

__all__ = ["attach_constraints"]


def attach_constraints(model: Model, model_file: ModelFile) -> Model:
    """Validate ``var`` bound qualifiers and attach them to the model."""
    constraints: dict[str, Bound] = {}
    for stmt in model_file.statements:
        if not isinstance(stmt, VarDecl) or stmt.constraint is None:
            continue
        lower, upper = stmt.constraint
        pos = stmt.names[0].pos if stmt.names else None
        if lower is None and upper is None:
            raise IRError("a var constraint must bound at least one side", pos)
        for bound in (lower, upper):
            if bound is not None:
                _validate_names(model, bound)
        _check_literal_order(lower, upper, pos)
        for ident in stmt.names:
            constraints[ident.name] = Bound(lower=lower, upper=upper)
    return replace(model, constraints=constraints)


def _validate_names(model: Model, expr: Expr) -> None:
    """Require every identifier in a bound to be a parameter or exogenous."""
    for ident in _identifiers(expr):
        name = ident.name
        if model.kind_of(name) is not None:
            raise IRError(
                f"bound may not reference endogenous variable {name!r}; bounds may "
                "only use parameters and exogenous variables",
                ident.pos,
            )
        if not (model.is_parameter(name) or model.is_exogenous(name)):
            raise IRError(f"bound references undeclared name {name!r}", ident.pos)


def _identifiers(expr: Expr) -> list[Identifier]:
    """Collect every identifier used as a value in ``expr`` (not call names)."""
    if isinstance(expr, Identifier):
        return [expr]
    if isinstance(expr, NumberLit):
        return []
    if isinstance(expr, UnaryOp):
        return _identifiers(expr.operand)
    if isinstance(expr, BinaryOp):
        return _identifiers(expr.left) + _identifiers(expr.right)
    if isinstance(expr, FunctionCall):
        idents: list[Identifier] = []
        for arg in expr.args:
            idents += _identifiers(arg)
        for kw in expr.kwargs:
            idents += _identifiers(kw.value)
        return idents
    return []


def _check_literal_order(lower: Expr | None, upper: Expr | None, pos) -> None:
    lo = _as_number(lower)
    hi = _as_number(upper)
    if lo is not None and hi is not None and lo >= hi:
        raise IRError(f"empty domain: lower bound {lo} is not below upper bound {hi}", pos)


def _as_number(expr: Expr | None) -> float | None:
    """Fold a literal (optionally negated) bound to a float, else ``None``."""
    if isinstance(expr, NumberLit):
        return expr.value
    if isinstance(expr, UnaryOp) and expr.op == "-" and isinstance(expr.operand, NumberLit):
        return -expr.operand.value
    return None

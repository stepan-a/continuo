"""Reduction of higher-order time derivatives to first order.

The collocation/BVP machinery downstream works on first-order systems, so
this pass rewrites every higher-order derivative using the standard
reduction trick. For ``diff(x, 2)`` it introduces an auxiliary variable
``__aux_diff_x_1`` standing for ``diff(x)``, adds the defining equation
``diff(x) = __aux_diff_x_1``, and rewrites ``diff(x, 2)`` as
``diff(__aux_diff_x_1)``. Order ``k`` introduces ``__aux_diff_x_1 …
__aux_diff_x_{k-1}`` and a chain of defining equations.

``diff(x, p)``, ``diff(x)`` and nested ``diff(diff(x))`` all denote a
time derivative of a single variable; the order composes additively
across nesting. ``diff(x, 0)`` is the identity, ``diff(x, 1)`` is
``diff(x)``, and a negative or non-integer order is rejected. An auxiliary
variable inherits the class (state or jump) of its base variable.

This runs before classification, so the checks downstream see a purely
first-order model.
"""

from __future__ import annotations

from continuo.ir.errors import IRError
from continuo.ir.model import Model
from continuo.parser.ast import (
    BinaryOp,
    DictEntry,
    DictLiteral,
    Equation,
    Expr,
    FunctionCall,
    Identifier,
    KeywordArg,
    NumberLit,
    SourcePos,
    UnaryOp,
    VarKind,
)

__all__ = ["reduce_orders", "aux_name", "AUX_PREFIX"]

AUX_PREFIX = "__aux_diff_"


def reduce_orders(model: Model) -> Model:
    """Return an equivalent model whose ``diff`` calls are all first order."""
    return _Reducer(model).run()


def aux_name(base: str, order: int) -> str:
    """The auxiliary state name standing for the ``order``-th derivative of ``base``."""
    return f"{AUX_PREFIX}{base}_{order}"


def _diff_call(name: str, pos: SourcePos | None) -> FunctionCall:
    return FunctionCall(Identifier("diff", pos), [Identifier(name, pos)], [], pos)


class _Reducer:
    def __init__(self, model: Model) -> None:
        self._model = model
        self._max_order: dict[str, int] = {}

    def run(self) -> Model:
        equations = [
            Equation(
                lhs=None if eq.lhs is None else self._rewrite(eq.lhs),
                rhs=self._rewrite(eq.rhs),
                tags=eq.tags,
                pos=eq.pos,
            )
            for eq in self._model.equations
        ]
        aux_states, aux_jumps, aux_equations, aux_origin = self._build_auxiliaries()
        return Model(
            states=self._model.states + tuple(aux_states),
            jumps=self._model.jumps + tuple(aux_jumps),
            algebraic=self._model.algebraic,
            exogenous=self._model.exogenous,
            parameters=self._model.parameters,
            parameter_values=self._model.parameter_values,
            equations=tuple(equations) + tuple(aux_equations),
            aux_origin=aux_origin,
        )

    # -- rewriting ----------------------------------------------------------

    def _rewrite(self, expr: Expr) -> Expr:
        if isinstance(expr, FunctionCall) and expr.name.name == "diff":
            subject, order = self._effective(expr)
            self._max_order[subject.name] = max(self._max_order.get(subject.name, 0), order)
            return self._reduced(subject, order)
        if isinstance(expr, UnaryOp):
            return UnaryOp(expr.op, self._rewrite(expr.operand), expr.pos)
        if isinstance(expr, BinaryOp):
            return BinaryOp(expr.op, self._rewrite(expr.left), self._rewrite(expr.right), expr.pos)
        if isinstance(expr, FunctionCall):
            return FunctionCall(
                expr.name,
                [self._rewrite(arg) for arg in expr.args],
                [KeywordArg(kw.name, self._rewrite(kw.value), kw.pos) for kw in expr.kwargs],
                expr.pos,
            )
        if isinstance(expr, DictLiteral):
            return DictLiteral(
                [DictEntry(e.key, self._rewrite(e.value), e.pos) for e in expr.entries],
                expr.pos,
            )
        return expr  # NumberLit, StringLit, Identifier

    def _reduced(self, subject: Identifier, order: int) -> Expr:
        if order == 0:
            return Identifier(subject.name, subject.pos)
        if order == 1:
            return _diff_call(subject.name, subject.pos)
        return _diff_call(aux_name(subject.name, order - 1), subject.pos)

    def _effective(self, call: FunctionCall) -> tuple[Identifier, int]:
        """The base variable and total derivative order of a ``diff`` call."""
        if not call.args:
            raise IRError("diff() requires an argument", call.pos)
        own = _order_value(call)
        arg = call.args[0]
        if isinstance(arg, FunctionCall) and arg.name.name == "diff":
            subject, inner = self._effective(arg)
            return subject, own + inner
        if isinstance(arg, Identifier):
            return arg, own
        raise IRError("diff() expects a variable as its first argument", call.pos)

    # -- auxiliary variables ------------------------------------------------

    def _build_auxiliaries(
        self,
    ) -> tuple[list[str], list[str], list[Equation], dict[str, tuple[str, int]]]:
        aux_states: list[str] = []
        aux_jumps: list[str] = []
        equations: list[Equation] = []
        aux_origin: dict[str, tuple[str, int]] = {}
        for base, order in self._max_order.items():
            if order < 2:
                continue
            bucket = self._aux_bucket(base, aux_states, aux_jumps)
            prev = base
            for j in range(1, order):
                aux = aux_name(base, j)
                equations.append(Equation(lhs=_diff_call(prev, None), rhs=Identifier(aux)))
                bucket.append(aux)
                aux_origin[aux] = (base, j)
                prev = aux
        return aux_states, aux_jumps, equations, aux_origin

    def _aux_bucket(self, base: str, aux_states: list[str], aux_jumps: list[str]) -> list[str]:
        kind = self._model.kind_of(base)
        if kind is VarKind.STATE:
            return aux_states
        if kind is VarKind.JUMP:
            return aux_jumps
        raise IRError(
            f"cannot take a second-or-higher time derivative of non-dynamic variable {base!r}"
        )


def _order_value(call: FunctionCall) -> int:
    if len(call.args) == 1:
        return 1
    if len(call.args) > 2 or call.kwargs:
        raise IRError("diff() takes one or two arguments", call.pos)
    node = call.args[1]
    if isinstance(node, UnaryOp) and node.op == "-" and isinstance(node.operand, NumberLit):
        raise IRError("diff() order must be non-negative", call.pos)
    if not isinstance(node, NumberLit):
        raise IRError("diff() order must be an integer literal", call.pos)
    if node.value != int(node.value):
        raise IRError("diff() order must be an integer", call.pos)
    return int(node.value)

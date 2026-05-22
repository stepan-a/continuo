"""Lowering model expressions to CasADi.

The model is a DAE ``F(ẋ, x, e, θ, t) = 0``. This module provides the
symbol table (one CasADi ``SX`` per endogenous variable, exogenous
process, parameter, the reserved time ``t``, and a time-derivative symbol
per state/jump) and :func:`translate`, which walks an AST expression and
builds the corresponding ``SX``. Assembling the residual vector and its
Jacobian from these pieces is a separate step.

The expression layer assumes the IR has already validated and reduced the
model: every ``diff`` is first order on a single variable, names resolve,
and the system is well-formed. The function library matches the model
language: arithmetic, comparison and logical operators; ``exp``, ``ln`` /
``log``, ``log10``, ``sqrt``, the trig and hyperbolic functions, ``erf``;
``abs``, ``sign``, ``min``, ``max``; and ``if(cond, a[, b])``.
"""

from __future__ import annotations

import operator
from dataclasses import dataclass, field

import casadi as ca

from dynare_ct.codegen.errors import CodegenError
from dynare_ct.ir.model import Model
from dynare_ct.parser.ast import (
    BinaryOp,
    DictLiteral,
    Expr,
    FunctionCall,
    Identifier,
    NumberLit,
    StringLit,
    UnaryOp,
)

__all__ = ["SymbolTable", "build_symbols", "translate"]

_TIME = "t"


@dataclass
class SymbolTable:
    """CasADi symbols for a model.

    ``symbols`` maps every endogenous variable, exogenous process,
    parameter and the reserved ``t`` to its ``SX``; ``derivatives`` maps a
    state/jump name to the ``SX`` standing for its time derivative.
    """

    symbols: dict[str, ca.SX] = field(default_factory=dict)
    derivatives: dict[str, ca.SX] = field(default_factory=dict)


def build_symbols(model: Model) -> SymbolTable:
    """Create the CasADi symbol table for ``model``."""
    table = SymbolTable()
    for name in (*model.endogenous, *model.exogenous, *model.parameters):
        table.symbols[name] = ca.SX.sym(name)
    table.symbols[_TIME] = ca.SX.sym(_TIME)  # reserved time variable
    for name in (*model.states, *model.jumps):
        table.derivatives[name] = ca.SX.sym(f"d_{name}")
    return table


# --- operators and functions ----------------------------------------------

_BINARY = {
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
    "/": operator.truediv,
    "^": operator.pow,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "==": operator.eq,
    "!=": operator.ne,
    "&&": ca.logic_and,
    "||": ca.logic_or,
}

_UNARY_FUNCTIONS = {
    "exp": ca.exp,
    "ln": ca.log,
    "log": ca.log,
    "log10": ca.log10,
    "sqrt": ca.sqrt,
    "sin": ca.sin,
    "cos": ca.cos,
    "tan": ca.tan,
    "asin": ca.asin,
    "acos": ca.acos,
    "atan": ca.atan,
    "sinh": ca.sinh,
    "cosh": ca.cosh,
    "tanh": ca.tanh,
    "abs": ca.fabs,
    "sign": ca.sign,
    "erf": ca.erf,
}

_VARIADIC_FUNCTIONS = {"min": ca.fmin, "max": ca.fmax}


def translate(expr: Expr, table: SymbolTable) -> ca.SX:
    """Lower an AST expression to a CasADi ``SX`` against ``table``."""
    if isinstance(expr, NumberLit):
        return ca.SX(expr.value)
    if isinstance(expr, Identifier):
        symbol = table.symbols.get(expr.name)
        if symbol is None:
            raise CodegenError(f"unknown symbol {expr.name!r} in model expression", expr.pos)
        return symbol
    if isinstance(expr, UnaryOp):
        operand = translate(expr.operand, table)
        return -operand if expr.op == "-" else ca.logic_not(operand)
    if isinstance(expr, BinaryOp):
        return _BINARY[expr.op](translate(expr.left, table), translate(expr.right, table))
    if isinstance(expr, FunctionCall):
        return _call(expr, table)
    if isinstance(expr, StringLit):
        raise CodegenError("a string literal has no numeric meaning in a model equation", expr.pos)
    if isinstance(expr, DictLiteral):
        raise CodegenError("a {…} mapping has no numeric meaning in a model equation", expr.pos)
    raise CodegenError(f"cannot translate {type(expr).__name__}")  # pragma: no cover


def _call(call: FunctionCall, table: SymbolTable) -> ca.SX:
    name = call.name.name
    if call.kwargs:
        raise CodegenError(f"{name}() keyword arguments are not allowed here", call.pos)
    if name == "diff":
        return _diff(call, table)
    if name == "if":
        return _if(call, table)
    args = [translate(arg, table) for arg in call.args]
    if name in _UNARY_FUNCTIONS:
        if len(args) != 1:
            raise CodegenError(f"{name}() takes exactly one argument", call.pos)
        return _UNARY_FUNCTIONS[name](args[0])
    if name in _VARIADIC_FUNCTIONS:
        if len(args) < 2:
            raise CodegenError(f"{name}() takes at least two arguments", call.pos)
        fold = _VARIADIC_FUNCTIONS[name]
        result = args[0]
        for arg in args[1:]:
            result = fold(result, arg)
        return result
    raise CodegenError(f"unknown function {name!r} in model expression", call.pos)


def _diff(call: FunctionCall, table: SymbolTable) -> ca.SX:
    # The IR has reduced every diff to first order on a single variable.
    if len(call.args) != 1 or not isinstance(call.args[0], Identifier):
        raise CodegenError("diff() expects a single variable", call.pos)
    name = call.args[0].name
    derivative = table.derivatives.get(name)
    if derivative is None:
        raise CodegenError(f"no time derivative defined for {name!r}", call.pos)
    return derivative


def _if(call: FunctionCall, table: SymbolTable) -> ca.SX:
    if not 2 <= len(call.args) <= 3:
        raise CodegenError("if() takes a condition and one or two branches", call.pos)
    args = [translate(arg, table) for arg in call.args]
    otherwise = args[2] if len(args) == 3 else ca.SX(0)
    return ca.if_else(args[0], args[1], otherwise)

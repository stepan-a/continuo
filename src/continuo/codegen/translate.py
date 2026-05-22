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

Shock-path expressions accept, in addition, a small library of named
shape helpers (``step``, ``pulse``, ``ramp``, ``bump``, ``expdecay``,
``smoothstep``). These are only meaningful as functions of time and are
rejected in ``model`` equations; a table built for a shock path sets
``in_shock_path`` to enable them.
"""

from __future__ import annotations

import operator
from dataclasses import dataclass, field

import casadi as ca

from continuo.codegen.errors import CodegenError
from continuo.ir.model import Model
from continuo.parser.ast import (
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
    ``in_shock_path`` is set when the table belongs to a shock-path
    expression, which enables the time-shape helper library.
    """

    symbols: dict[str, ca.SX] = field(default_factory=dict)
    derivatives: dict[str, ca.SX] = field(default_factory=dict)
    in_shock_path: bool = False


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


# --- shock-path shape helpers ----------------------------------------------
#
# Sugars for the shapes that recur in shock paths, each an explicit function
# of time. They are available only in shock-path expressions (the parser sees
# their discontinuity locations in the arguments), never in model equations.


def _step(t: ca.SX, t0: ca.SX) -> ca.SX:
    """Unit step: 0 before ``t0``, 1 from ``t0`` on."""
    return ca.if_else(t >= t0, 1, 0)


def _pulse(t: ca.SX, t0: ca.SX, t1: ca.SX) -> ca.SX:
    """Rectangular pulse: 1 on ``[t0, t1)``, 0 elsewhere."""
    return ca.if_else(ca.logic_and(t >= t0, t < t1), 1, 0)


def _ramp(t: ca.SX, t0: ca.SX, t1: ca.SX) -> ca.SX:
    """Saturating ramp: 0 before ``t0``, linear to 1 over ``[t0, t1]``, then 1."""
    return ca.fmin(ca.fmax((t - t0) / (t1 - t0), 0), 1)


def _bump(t: ca.SX, t0: ca.SX, t1: ca.SX) -> ca.SX:
    """Smooth (C-infinity) bump on ``(t0, t1)``: 0 outside, peak 1 at the centre."""
    x = (t - (t0 + t1) / 2) / ((t1 - t0) / 2)
    inside = x * x < 1
    safe = ca.if_else(inside, 1 - x * x, 1)  # keep the exponent finite outside
    return ca.if_else(inside, ca.exp(1 - 1 / safe), 0)


def _expdecay(t: ca.SX, t0: ca.SX, tau: ca.SX) -> ca.SX:
    """Exponential decay: 0 before ``t0``, ``exp(-(t-t0)/tau)`` (so 1 at ``t0``) after."""
    return ca.if_else(t >= t0, ca.exp(-(t - t0) / tau), 0)


def _smoothstep(t: ca.SX, t0: ca.SX, k: ca.SX) -> ca.SX:
    """Logistic step centred at ``t0`` with steepness ``k`` (0.5 at ``t0``)."""
    return 1 / (1 + ca.exp(-k * (t - t0)))


# name -> (argument count, builder)
_SHOCK_HELPERS = {
    "step": (2, _step),
    "pulse": (3, _pulse),
    "ramp": (3, _ramp),
    "bump": (3, _bump),
    "expdecay": (3, _expdecay),
    "smoothstep": (3, _smoothstep),
}


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
    if name in _SHOCK_HELPERS:
        if not table.in_shock_path:
            raise CodegenError(
                f"{name}() is a shock-path helper and is not available in model equations",
                call.pos,
            )
        arity, builder = _SHOCK_HELPERS[name]
        if len(args) != arity:
            raise CodegenError(f"{name}() takes exactly {arity} arguments", call.pos)
        return builder(*args)
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

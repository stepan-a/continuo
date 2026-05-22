"""Assembling the model residual and its Jacobians.

The model is the DAE ``F(ẋ, x, e, θ, t) = 0``. This module stacks the
per-equation residuals — ``lhs - rhs`` for an explicit equation, ``expr``
for a bare ``expr;`` (which means ``expr == 0``) — into the vector ``F``
and derives its Jacobians by CasADi automatic differentiation.

Vector orderings:

- ``x``     : endogenous variables in ``model.endogenous`` order;
- ``ẋ``     : time derivatives, states then jumps (the variables that have one);
- ``e``     : exogenous processes in ``model.exogenous`` order;
- ``θ``     : parameters in ``model.parameters`` order;
- ``t``     : the scalar reserved time.

The result holds CasADi ``Function`` objects for ``F`` and for ``∂F/∂x``
and ``∂F/∂ẋ`` (the blocks the collocation Newton needs). C codegen and
JIT compilation of these are a later step.
"""

from __future__ import annotations

from dataclasses import dataclass

import casadi as ca

from continuo.codegen.translate import SymbolTable, build_symbols, translate
from continuo.ir.model import Model

__all__ = ["Residual", "build_residual"]


@dataclass
class Residual:
    """The symbolic residual ``F`` of a model and its Jacobians, as CasADi.

    ``function`` maps ``(ẋ, x, e, θ, t)`` to the residual vector;
    ``jacobian_x`` and ``jacobian_xdot`` map the same inputs to ``∂F/∂x``
    and ``∂F/∂ẋ`` respectively.
    """

    symbols: SymbolTable
    expression: ca.SX
    function: ca.Function
    jacobian_x: ca.Function
    jacobian_xdot: ca.Function


def build_residual(model: Model) -> Residual:
    """Build the residual ``F`` and its Jacobians for ``model``."""
    table = build_symbols(model)

    residuals = [_residual(eq, table) for eq in model.equations]
    F = _column(residuals)

    x = _column([table.symbols[name] for name in model.endogenous])
    xdot = _column([table.derivatives[name] for name in (*model.states, *model.jumps)])
    e = _column([table.symbols[name] for name in model.exogenous])
    theta = _column([table.symbols[name] for name in model.parameters])
    t = table.symbols["t"]

    inputs = [xdot, x, e, theta, t]
    names = ["xdot", "x", "e", "theta", "t"]
    function = ca.Function("F", inputs, [F], names, ["F"])
    jacobian_x = ca.Function("jac_x", inputs, [ca.jacobian(F, x)], names, ["jac_x"])
    jacobian_xdot = ca.Function("jac_xdot", inputs, [ca.jacobian(F, xdot)], names, ["jac_xdot"])

    return Residual(table, F, function, jacobian_x, jacobian_xdot)


def _residual(eq, table: SymbolTable) -> ca.SX:
    if eq.lhs is None:  # bare `expr;` means expr == 0
        return translate(eq.rhs, table)
    return translate(eq.lhs, table) - translate(eq.rhs, table)


def _column(symbols: list[ca.SX]) -> ca.SX:
    return ca.vertcat(*symbols) if symbols else ca.SX.zeros(0, 1)

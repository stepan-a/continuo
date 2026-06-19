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
    and ``∂F/∂ẋ`` respectively. ``dynamic_rows`` / ``algebraic_rows`` are the
    row indices of ``F`` that do / do not depend on ``ẋ``, and
    ``dynamic_function`` / ``algebraic_function`` return just those rows — so a
    caller needing only one block (the stacked system's pointwise algebraic
    rows, the residual monitor's dynamic defect) does not evaluate the other.
    """

    symbols: SymbolTable
    expression: ca.SX
    function: ca.Function
    jacobian_x: ca.Function
    jacobian_xdot: ca.Function
    dynamic_rows: tuple[int, ...]
    algebraic_rows: tuple[int, ...]
    dynamic_function: ca.Function
    algebraic_function: ca.Function


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
    # Differentiate F once w.r.t. (x, ẋ) and split the columns, then assemble F
    # and both Jacobian blocks as a single multi-output Function so CasADi shares
    # one common-subexpression graph (and one C-codegen unit) across them. The
    # three public views are pruned single-output factories, so a caller that
    # needs only F — or only ∂F/∂x — does not evaluate the other blocks.
    nx = x.size1()
    jac = ca.jacobian(F, ca.vertcat(x, xdot))
    combined = ca.Function(
        "F_all", inputs, [F, jac[:, :nx], jac[:, nx:]], names, ["F", "jac_x", "jac_xdot"]
    )
    function = combined.factory("F", names, ["F"])
    jacobian_x = combined.factory("jac_x", names, ["jac_x"])
    jacobian_xdot = combined.factory("jac_xdot", names, ["jac_xdot"])

    # Split F's rows into those that depend on ẋ (dynamic) and those that do not
    # (algebraic), and build a Function for each block, so a caller needing only
    # one — the stacked system's pointwise algebraic rows, the monitor's dynamic
    # defect — neither evaluates nor builds the graph for the other.
    if xdot.numel() == 0:
        dynamic_rows: tuple[int, ...] = ()
        algebraic_rows: tuple[int, ...] = tuple(range(F.size1()))
    else:
        depends = ca.which_depends(F, xdot, 1, True)
        dynamic_rows = tuple(r for r, d in enumerate(depends) if d)
        algebraic_rows = tuple(r for r, d in enumerate(depends) if not d)
    dyn_expr = ca.vertcat(*(F[r] for r in dynamic_rows)) if dynamic_rows else ca.SX.zeros(0, 1)
    alg_expr = ca.vertcat(*(F[r] for r in algebraic_rows)) if algebraic_rows else ca.SX.zeros(0, 1)
    dynamic_function = ca.Function("F_dyn", inputs, [dyn_expr], names, ["F_dyn"])
    algebraic_function = ca.Function("F_alg", inputs, [alg_expr], names, ["F_alg"])

    return Residual(
        table,
        F,
        function,
        jacobian_x,
        jacobian_xdot,
        dynamic_rows,
        algebraic_rows,
        dynamic_function,
        algebraic_function,
    )


def _residual(eq, table: SymbolTable) -> ca.SX:
    if eq.lhs is None:  # bare `expr;` means expr == 0
        return translate(eq.rhs, table)
    return translate(eq.lhs, table) - translate(eq.rhs, table)


def _column(symbols: list[ca.SX]) -> ca.SX:
    return ca.vertcat(*symbols) if symbols else ca.SX.zeros(0, 1)

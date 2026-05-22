"""Shared numeric-evaluation helpers for the solvers.

Turning a (constant) model expression — a parameter value, a steady-state
formula, an initial condition — into a number reuses the codegen
translator: bind the known names to constant CasADi symbols, translate,
and evaluate with ``ca.evalf``. Both the steady-state solver and the
perfect-foresight driver build their constant environments this way.
"""

from __future__ import annotations

import casadi as ca

from continuo.codegen.errors import CodegenError
from continuo.codegen.translate import SymbolTable, translate
from continuo.ir.model import Model
from continuo.parser.ast import Expr
from continuo.solve.errors import SolveError

__all__ = ["constant_table", "eval_constant"]


def constant_table(theta: dict[str, float], e: dict[str, float], model: Model) -> SymbolTable:
    """A symbol table binding parameters, exogenous and ``t`` to constants."""
    table = SymbolTable()
    for name, value in theta.items():
        table.symbols[name] = ca.SX(value)
    for name in model.exogenous:
        table.symbols[name] = ca.SX(e.get(name, 0.0))
    table.symbols["t"] = ca.SX(0.0)  # the steady state / boundary data is time-invariant
    return table


def eval_constant(expr: Expr, table: SymbolTable, *, what: str) -> float:
    """Evaluate a constant expression to a float, mapping failures to SolveError."""
    try:
        return float(ca.evalf(translate(expr, table)))
    except CodegenError as exc:
        raise SolveError(f"{what}: {exc}") from None
    except RuntimeError as exc:  # a non-constant expression slipped through
        raise SolveError(f"{what} is not a constant: {exc}") from None

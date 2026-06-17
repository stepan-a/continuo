"""Intermediate representation: AST → Model object the solvers consume.

Public API::

    from continuo.ir import build
    model = build(ast)   # ast from continuo.parser.parse(...)
"""

from __future__ import annotations

from continuo.ir.boundary import attach_boundary
from continuo.ir.build import build
from continuo.ir.classify import classify
from continuo.ir.commands import attach_commands
from continuo.ir.constraints import attach_constraints
from continuo.ir.errors import IRError
from continuo.ir.model import Bound, Model, Shock, ShockPath, Simulation, SteadyQuery
from continuo.ir.reduce import reduce_orders
from continuo.ir.shocks import attach_shocks
from continuo.ir.steady_state import attach_steady_state

__all__ = [
    "build",
    "classify",
    "reduce_orders",
    "attach_boundary",
    "attach_steady_state",
    "attach_constraints",
    "attach_shocks",
    "attach_commands",
    "Bound",
    "Model",
    "Shock",
    "ShockPath",
    "Simulation",
    "SteadyQuery",
    "IRError",
]

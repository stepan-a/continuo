"""Intermediate representation: AST → Model object the solvers consume.

Public API::

    from dynare_ct.ir import build
    model = build(ast)   # ast from dynare_ct.parser.parse(...)
"""

from __future__ import annotations

from dynare_ct.ir.boundary import attach_boundary
from dynare_ct.ir.build import build
from dynare_ct.ir.classify import classify
from dynare_ct.ir.commands import attach_commands
from dynare_ct.ir.errors import IRError
from dynare_ct.ir.model import Model, Shock, ShockPath, Simulation, SteadyQuery
from dynare_ct.ir.reduce import reduce_orders
from dynare_ct.ir.shocks import attach_shocks
from dynare_ct.ir.steady_state import attach_steady_state

__all__ = [
    "build",
    "classify",
    "reduce_orders",
    "attach_boundary",
    "attach_steady_state",
    "attach_shocks",
    "attach_commands",
    "Model",
    "Shock",
    "ShockPath",
    "Simulation",
    "SteadyQuery",
    "IRError",
]

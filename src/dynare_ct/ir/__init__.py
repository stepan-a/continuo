"""Intermediate representation: AST → Model object the solvers consume.

Public API::

    from dynare_ct.ir import build
    model = build(ast)   # ast from dynare_ct.parser.parse(...)
"""

from __future__ import annotations

from dynare_ct.ir.build import build
from dynare_ct.ir.classify import classify
from dynare_ct.ir.errors import IRError
from dynare_ct.ir.model import Model
from dynare_ct.ir.reduce import reduce_orders

__all__ = ["build", "classify", "reduce_orders", "Model", "IRError"]

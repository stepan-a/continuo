"""IR → CasADi expressions.

Lowers a validated :class:`~dynare_ct.ir.model.Model` to CasADi symbolic
expressions, from which the residual and its Jacobian are derived and
(later) C-codegen'd. CasADi is an implementation detail — toolbox users
never see it.

Public API so far::

    from dynare_ct.codegen import build_symbols, translate
    table = build_symbols(model)
    sx = translate(expression, table)
"""

from __future__ import annotations

from dynare_ct.codegen.errors import CodegenError
from dynare_ct.codegen.residual import Residual, build_residual
from dynare_ct.codegen.translate import SymbolTable, build_symbols, translate

__all__ = [
    "build_symbols",
    "translate",
    "build_residual",
    "SymbolTable",
    "Residual",
    "CodegenError",
]

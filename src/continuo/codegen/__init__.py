"""IR → CasADi expressions.

Lowers a validated :class:`~continuo.ir.model.Model` to CasADi symbolic
expressions, from which the residual and its Jacobian are derived and
(later) C-codegen'd. CasADi is an implementation detail — toolbox users
never see it.

Public API so far::

    from continuo.codegen import build_symbols, translate
    table = build_symbols(model)
    sx = translate(expression, table)
"""

from __future__ import annotations

from continuo.codegen.errors import CodegenError
from continuo.codegen.native import CompiledResidual, compile_residual
from continuo.codegen.residual import Residual, build_residual
from continuo.codegen.translate import SymbolTable, build_symbols, translate

__all__ = [
    "build_symbols",
    "translate",
    "build_residual",
    "compile_residual",
    "SymbolTable",
    "Residual",
    "CompiledResidual",
    "CodegenError",
]

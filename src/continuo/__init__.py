"""continuo: continuous-time DSGE toolbox in the spirit of Dynare.

import continuo
model = continuo.parse("model.mod")
sol = model.simul()
sol["C"]            # the consumption path
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from continuo.api import Model, parse, parse_string
from continuo.codegen import CodegenError
from continuo.io import Solution
from continuo.ir import IRError
from continuo.macro import MacroError
from continuo.solve import SolveError

try:
    __version__ = version("continuo")
except PackageNotFoundError:  # pragma: no cover - source checkout without install
    __version__ = "0.0.0"

__all__ = [
    "parse",
    "parse_string",
    "Model",
    "Solution",
    "MacroError",
    "IRError",
    "CodegenError",
    "SolveError",
    "__version__",
]

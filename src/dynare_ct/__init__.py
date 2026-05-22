"""dynare-ct: continuous-time DSGE toolbox in the spirit of Dynare.

import dynare_ct
model = dynare_ct.parse("model.mod")
sol = model.simul()
sol["C"]            # the consumption path
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from dynare_ct.api import Model, parse, parse_string
from dynare_ct.codegen import CodegenError
from dynare_ct.io import Solution
from dynare_ct.ir import IRError
from dynare_ct.macro import MacroError
from dynare_ct.solve import SolveError

try:
    __version__ = version("dynare-ct")
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

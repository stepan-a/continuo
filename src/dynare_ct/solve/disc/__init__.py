"""Discretisation schemes (Crank-Nicolson, with Radau / Lobatto-IIIA later).

Public API::

    from dynare_ct.solve.disc import uniform_grid, crank_nicolson_residual
"""

from __future__ import annotations

from dynare_ct.solve.disc.crank_nicolson import crank_nicolson_residual
from dynare_ct.solve.disc.grid import Grid, uniform_grid

__all__ = ["uniform_grid", "Grid", "crank_nicolson_residual"]

"""Discretisation schemes for the perfect-foresight collocation.

Public API::

    from continuo.solve.disc import uniform_grid, crank_nicolson_residual
    from continuo.solve.disc import collocation_residual, tableau_for

``crank_nicolson`` is the default one-stage scheme; the collocation
families ``gauss`` / ``radau`` / ``lobatto_iiia`` are built from Butcher
tableaux (:mod:`continuo.solve.disc.tableaux`) and discretised by
:func:`collocation_residual`.
"""

from __future__ import annotations

from continuo.solve.disc.collocation import collocation_residual
from continuo.solve.disc.crank_nicolson import crank_nicolson_residual
from continuo.solve.disc.grid import Grid, uniform_grid
from continuo.solve.disc.tableaux import (
    SCHEME_ORDERS,
    ButcherTableau,
    default_order,
    gauss,
    lobatto_iiia,
    radau_iia,
    tableau_for,
)

# Discretisation schemes continuo can build (crank_nicolson plus the
# collocation families). The orchestrator gates which are wired into a solve.
SCHEMES = ("crank_nicolson", "gauss", "radau", "lobatto_iiia")

__all__ = [
    "uniform_grid",
    "Grid",
    "crank_nicolson_residual",
    "collocation_residual",
    "ButcherTableau",
    "gauss",
    "radau_iia",
    "lobatto_iiia",
    "tableau_for",
    "default_order",
    "SCHEME_ORDERS",
    "SCHEMES",
]

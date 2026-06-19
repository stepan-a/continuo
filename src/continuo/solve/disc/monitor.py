"""Error monitors for grid adequacy and (later) adaptive refinement.

A monitor turns a solved trajectory on a grid into a per-interval **error
indicator** (where the mesh is hardest) and, where it can, a global error
**estimate** (a magnitude for a tolerance test). The per-interval indicator
drives the *equidistribution ratio* ``max/mean`` — a cheap "is the mesh
balanced / would refinement help?" diagnostic — and, in the adaptive loop,
tells the refiner where to add nodes.

Three presets, mirroring the solver registries
(:func:`~continuo.solve.rootfind.select_steady_solver`):

- ``curvature`` — equidistribute ``|x″|`` estimated from the node values.
  Indicator only (no magnitude), free, scheme-agnostic; the always-on
  diagnostic.
- ``richardson`` — compare the solution against one on a refined mesh and
  scale by the scheme order ``p``. A calibrated error magnitude,
  scheme-agnostic (covers Crank–Nicolson). Needs the refined solution
  supplied (the caller runs it).
- ``residual`` — the ODE defect of a smooth (cubic-spline) interpolant of the
  node values. An indicator, scheme-agnostic; needs a callable evaluating the
  model's dynamic residual. (A scheme-*calibrated* variant — bvp5c's exact
  Lobatto IIIA residual↔error relation, which needs the collocation
  interpolant's own stage values — is a later refinement.)

This module deliberately depends only on the grid and arrays (plus a caller
supplied residual callable), not on the solver, so it carries no risk of an
import cycle.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np
from scipy.interpolate import CubicSpline

from continuo.solve.disc.grid import Grid
from continuo.solve.errors import SolveError

__all__ = [
    "GridError",
    "MonitorInput",
    "Monitor",
    "CurvatureMonitor",
    "RichardsonMonitor",
    "ResidualMonitor",
    "MONITORS",
    "select_monitor",
    "equidistribution_ratio",
]

# A dynamic-residual callable: ``(t, x_full, xdot_dynamic) -> residual vector``
# of the model's dynamic rows. Built by the caller from the codegen residual.
DynamicResidual = Callable[[float, np.ndarray, np.ndarray], np.ndarray]

_FLOOR = 1e-300  # keep per-interval weights strictly positive for ratios


@dataclass(frozen=True)
class GridError:
    """A per-interval error indicator and (optionally) a global estimate.

    ``per_interval`` has one entry per interval (``N``); ``estimate`` is a
    global error magnitude when the monitor produces one, else ``None``.
    """

    per_interval: np.ndarray
    estimate: float | None = None

    @property
    def equidistribution_ratio(self) -> float:
        """``max/mean`` of the indicator: ``≈1`` balanced, ``≫1`` misallocated."""
        weights = self.per_interval
        mean = float(np.mean(weights)) if weights.size else 0.0
        return float(np.max(weights) / mean) if mean > 0 else 1.0


@dataclass
class MonitorInput:
    """Everything a monitor might need; each preset uses the relevant fields."""

    grid: Grid
    path: np.ndarray  # (N+1, n) node values
    order: int | None = None  # scheme order p; required by Richardson, unused elsewhere
    refined: tuple[Grid, np.ndarray] | None = None  # (bisected grid, its path)
    dynamic_residual: DynamicResidual | None = None  # for the residual monitor
    n_dynamic: int = 0


@runtime_checkable
class Monitor(Protocol):
    """Estimates grid error from a solved segment."""

    name: str

    def assess(self, data: MonitorInput) -> GridError: ...


@dataclass(frozen=True)
class CurvatureMonitor:
    name: str = "curvature"

    def assess(self, data: MonitorInput) -> GridError:
        return _curvature(data.grid, data.path)


@dataclass(frozen=True)
class RichardsonMonitor:
    name: str = "richardson"

    def assess(self, data: MonitorInput) -> GridError:
        if data.refined is None:
            raise SolveError("the richardson monitor needs a refined solution")
        if data.order is None:
            raise SolveError("the richardson monitor needs the scheme order")
        return _richardson(data.path, data.refined[1], data.order)


@dataclass(frozen=True)
class ResidualMonitor:
    name: str = "residual"

    def assess(self, data: MonitorInput) -> GridError:
        if data.dynamic_residual is None:
            raise SolveError("the residual monitor needs a dynamic-residual callable")
        return _residual(data.grid, data.path, data.dynamic_residual, data.n_dynamic)


MONITORS: dict[str, Monitor] = {
    m.name: m for m in (CurvatureMonitor(), RichardsonMonitor(), ResidualMonitor())
}


def select_monitor(name: str) -> Monitor:
    """Return the monitor preset ``name``; raise :class:`SolveError` if unknown."""
    try:
        return MONITORS[name]
    except KeyError:
        raise SolveError(
            f"unknown error monitor {name!r}; expected one of {', '.join(sorted(MONITORS))}"
        ) from None


# ---------------------------------------------------------------------------
# implementations
# ---------------------------------------------------------------------------


def equidistribution_ratio(points: np.ndarray, path: np.ndarray) -> float:
    """Curvature ``max/mean`` over a solved path — the grid-adequacy diagnostic.

    Returns ``1.0`` for a path too short to assess (fewer than three nodes).
    """
    if len(points) < 3:
        return 1.0
    grid = Grid(points=np.asarray(points, dtype=float))
    return CurvatureMonitor().assess(MonitorInput(grid=grid, path=path)).equidistribution_ratio


def _scaled(path: np.ndarray) -> np.ndarray:
    """Per-variable scale (the range) so components contribute comparably."""
    span = np.ptp(path, axis=0)
    return np.where(span > 0, span, 1.0)


def _curvature(grid: Grid, path: np.ndarray) -> GridError:
    points = grid.points
    h = grid.steps
    if len(points) < 3:  # too few nodes to estimate a second derivative
        return GridError(per_interval=np.maximum(h, _FLOOR))
    y = path / _scaled(path)
    d2 = np.zeros_like(y)
    hm, hp = h[:-1, None], h[1:, None]  # left/right step at each interior node
    d2[1:-1] = 2.0 * ((y[2:] - y[1:-1]) / hp - (y[1:-1] - y[:-2]) / hm) / (hm + hp)
    d2[0], d2[-1] = d2[1], d2[-2]
    curv = np.max(np.abs(d2), axis=1)  # node curvature, reduced over variables
    per_interval = h * 0.5 * (curv[:-1] + curv[1:])
    return GridError(per_interval=np.maximum(per_interval, _FLOOR))


def _richardson(coarse_path: np.ndarray, fine_path: np.ndarray, order: int) -> GridError:
    # The refined mesh bisects each interval, so the coarse nodes are the
    # even-indexed fine nodes. With both errors ~ C·hᵖ, the error of the coarse
    # solution is the gap scaled by 2ᵖ/(2ᵖ−1) (Richardson extrapolation).
    fine_at_coarse = fine_path[::2]
    if fine_at_coarse.shape != coarse_path.shape:
        raise SolveError("richardson monitor expects the refined mesh to bisect each interval")
    factor = 2**order / (2**order - 1)
    node_err = np.max(np.abs(coarse_path - fine_at_coarse), axis=1) * factor
    per_interval = 0.5 * (node_err[:-1] + node_err[1:])
    return GridError(per_interval=np.maximum(per_interval, _FLOOR), estimate=float(node_err.max()))


def _residual(
    grid: Grid, path: np.ndarray, dynamic_residual: DynamicResidual, n_dynamic: int
) -> GridError:
    # Defect of a smooth interpolant: fit a cubic spline through the node
    # values, then measure the model's dynamic residual at the interval
    # midpoints with the spline's value and derivative.
    spline = CubicSpline(grid.points, path, axis=0)
    mids = grid.midpoints
    x_mid = spline(mids)
    xdot_mid = spline(mids, 1)[:, :n_dynamic]
    defect = np.array(
        [
            np.max(np.abs(dynamic_residual(float(t), x_mid[i], xdot_mid[i])))
            for i, t in enumerate(mids)
        ]
    )
    return GridError(per_interval=np.maximum(defect, _FLOOR), estimate=float(defect.max()))

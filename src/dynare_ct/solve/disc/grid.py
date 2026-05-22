"""Time grids for the perfect-foresight solve.

A grid over ``[0, T]`` with ``N`` intervals: ``N + 1`` points ``t₀ … t_N``
with spacing ``dt = T/N``, and the ``N`` interval midpoints the
Crank–Nicolson scheme evaluates at. Multi-segment grids (with reveal-time
breakpoints) are built by the orchestrator on top of this.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from dynare_ct.solve.errors import SolveError

__all__ = ["Grid", "uniform_grid"]


@dataclass(eq=False)
class Grid:
    """A uniform time grid: ``points`` (N+1), ``midpoints`` (N), and ``dt``."""

    points: np.ndarray
    midpoints: np.ndarray
    dt: float

    @property
    def intervals(self) -> int:
        return len(self.midpoints)


def uniform_grid(horizon: float, intervals: int) -> Grid:
    """Build a uniform grid over ``[0, horizon]`` with ``intervals`` intervals."""
    if horizon <= 0:
        raise SolveError("simulation horizon T must be positive")
    if intervals < 1:
        raise SolveError("number of grid intervals N must be at least 1")
    points = np.linspace(0.0, float(horizon), intervals + 1)
    midpoints = 0.5 * (points[:-1] + points[1:])
    return Grid(points=points, midpoints=midpoints, dt=float(horizon) / intervals)

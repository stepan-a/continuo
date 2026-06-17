"""Time grids for the perfect-foresight solve.

A grid over ``[t₀, t_N]`` is just its ``N + 1`` node positions; the
per-interval steps, the interval midpoints (which Crank–Nicolson evaluates
at), and the interval count are derived from them. The nodes need not be
equally spaced — :func:`uniform_grid` builds the equal-step default, and
:func:`mesh_from_points` wraps an arbitrary increasing node sequence (for a
graded or refined mesh). Multi-segment grids (with reveal-time breakpoints)
are built by the orchestrator on top of these.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from continuo.solve.errors import SolveError

__all__ = ["Grid", "uniform_grid", "mesh_from_points", "aligned_grid"]


@dataclass(eq=False)
class Grid:
    """A time grid, defined by its strictly increasing node positions.

    ``steps`` (the ``N`` per-interval widths), ``midpoints`` (the ``N``
    interval midpoints) and ``intervals`` (``N``) are derived from
    ``points`` (``N + 1`` nodes), so a non-uniform mesh is just a ``points``
    array with unequal gaps.
    """

    points: np.ndarray

    @property
    def steps(self) -> np.ndarray:
        """The ``N`` per-interval widths ``tᵢ₊₁ − tᵢ``."""
        return np.diff(self.points)

    @property
    def midpoints(self) -> np.ndarray:
        """The ``N`` interval midpoints."""
        return 0.5 * (self.points[:-1] + self.points[1:])

    @property
    def intervals(self) -> int:
        return len(self.points) - 1

    @property
    def dt(self) -> float:
        """The single step of a uniform grid; raises for a non-uniform mesh."""
        steps = self.steps
        if not np.allclose(steps, steps[0]):
            raise ValueError("non-uniform grid has no single dt; use .steps")
        return float(steps[0])


def uniform_grid(horizon: float, intervals: int, start: float = 0.0) -> Grid:
    """Build a uniform grid over ``[start, start + horizon]`` with ``intervals`` intervals.

    ``start`` offsets the grid so a simulation segment beginning at a
    reveal time uses absolute times (the shock paths and ``t`` are in
    absolute time).
    """
    if horizon <= 0:
        raise SolveError("simulation horizon T must be positive")
    if intervals < 1:
        raise SolveError("number of grid intervals N must be at least 1")
    return Grid(points=float(start) + np.linspace(0.0, float(horizon), intervals + 1))


def mesh_from_points(points: np.ndarray) -> Grid:
    """Wrap an arbitrary strictly-increasing node sequence as a :class:`Grid`."""
    pts = np.asarray(points, dtype=float)
    if pts.ndim != 1 or len(pts) < 2:
        raise SolveError("a grid needs at least two points")
    if np.any(np.diff(pts) <= 0):
        raise SolveError("grid points must be strictly increasing")
    return Grid(points=pts)


def aligned_grid(start: float, horizon: float, intervals: int, mark: float) -> tuple[Grid, int]:
    """A mesh on ``[start, start + horizon]`` (``intervals`` intervals) with a node at ``mark``.

    Returns the grid and the index of the ``mark`` node — the next reveal time
    of a segment, or the terminal time ``T`` for the last one — so it falls on
    a node instead of being snapped to the nearest one. When ``mark`` is the far
    end (or ``intervals < 2``) the mesh is uniform.
    """
    far = start + horizon
    if intervals < 2 or mark >= far:
        return uniform_grid(horizon, intervals, start=start), intervals
    m = min(max(int(round(intervals * (mark - start) / horizon)), 1), intervals - 1)
    left = np.linspace(start, mark, m + 1)
    right = np.linspace(mark, far, intervals - m + 1)
    return mesh_from_points(np.concatenate([left, right[1:]])), m

"""Tests for the uniform time grid."""

from __future__ import annotations

import pytest

from continuo.solve import SolveError
from continuo.solve.disc import uniform_grid


def test_uniform_grid_layout():
    grid = uniform_grid(10.0, 5)
    assert grid.dt == pytest.approx(2.0)
    assert len(grid.points) == 6
    assert grid.points[0] == pytest.approx(0.0)
    assert grid.points[-1] == pytest.approx(10.0)
    assert len(grid.midpoints) == 5
    assert grid.midpoints[0] == pytest.approx(1.0)
    assert grid.intervals == 5


def test_midpoints_lie_between_points():
    grid = uniform_grid(1.0, 4)
    for i, mid in enumerate(grid.midpoints):
        assert grid.points[i] < mid < grid.points[i + 1]


def test_non_positive_horizon_rejected():
    with pytest.raises(SolveError, match="horizon T must be positive"):
        uniform_grid(0.0, 5)


def test_zero_intervals_rejected():
    with pytest.raises(SolveError, match="at least 1"):
        uniform_grid(10.0, 0)

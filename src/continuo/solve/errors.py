"""Solver error type.

Raised when a numerical step fails — a steady state that does not
converge, a singular Jacobian, a parameter left without a value, and so
on. Distinct from the symbolic/structural errors of the earlier layers:
by the time the solver runs the model is valid, so a :class:`SolveError`
is about the numerics, not the model's well-formedness.
"""

from __future__ import annotations

__all__ = ["SolveError"]


class SolveError(Exception):
    """A numerical solve failure."""

"""Solvers: steady state, perfect-foresight BVP, multi-segment orchestration.

Public API::

    from dynare_ct.solve import simulate, steady_state
    sol = simulate(model)              # reads the simulate command
    ss = steady_state(model, exogenous={...})
"""

from __future__ import annotations

from dynare_ct.io.solution import Solution
from dynare_ct.solve.errors import SolveError
from dynare_ct.solve.orchestrator import simulate
from dynare_ct.solve.pf import solve_pf, solve_segment
from dynare_ct.solve.steady import evaluate_parameters, steady_state

__all__ = [
    "simulate",
    "steady_state",
    "evaluate_parameters",
    "solve_pf",
    "solve_segment",
    "Solution",
    "SolveError",
]

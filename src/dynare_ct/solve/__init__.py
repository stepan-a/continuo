"""Solvers: steady state, perfect-foresight BVP, multi-segment orchestration.

Public API so far::

    from dynare_ct.solve import steady_state
    ss = steady_state(model, exogenous={...})
"""

from __future__ import annotations

from dynare_ct.solve.errors import SolveError
from dynare_ct.solve.orchestrator import simulate
from dynare_ct.solve.pf import PFSolution, solve_pf, solve_segment
from dynare_ct.solve.steady import evaluate_parameters, steady_state

__all__ = [
    "simulate",
    "steady_state",
    "evaluate_parameters",
    "solve_pf",
    "solve_segment",
    "PFSolution",
    "SolveError",
]

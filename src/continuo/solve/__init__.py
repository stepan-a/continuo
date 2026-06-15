"""Solvers: steady state, perfect-foresight BVP, multi-segment orchestration.

Public API::

    from continuo.solve import simulate, steady_state
    sol = simulate(model)              # reads the simulate command
    ss = steady_state(model, exogenous={...})
"""

from __future__ import annotations

from continuo.io.solution import Solution
from continuo.solve.errors import SolveError
from continuo.solve.linsolve import (
    SOLVERS,
    LinearSolver,
    SuperluSolver,
    available_solvers,
    select_solver,
)
from continuo.solve.orchestrator import simulate
from continuo.solve.pf import solve_pf, solve_segment
from continuo.solve.steady import evaluate_parameters, steady_state

__all__ = [
    "simulate",
    "steady_state",
    "evaluate_parameters",
    "solve_pf",
    "solve_segment",
    "Solution",
    "SolveError",
    "LinearSolver",
    "SuperluSolver",
    "SOLVERS",
    "available_solvers",
    "select_solver",
]

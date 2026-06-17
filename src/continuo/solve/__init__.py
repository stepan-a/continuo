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
    KluSolver,
    LinearSolver,
    PardisoSolver,
    SuperluSolver,
    UmfpackSolver,
    available_solvers,
    select_solver,
)
from continuo.solve.orchestrator import simulate
from continuo.solve.pf import solve_pf, solve_segment
from continuo.solve.rootfind import (
    STEADY_SOLVERS,
    AutoSolver,
    HomotopySolver,
    KinsolSolver,
    NewtonSolver,
    RootProblem,
    RootResult,
    ScipyRootSolver,
    SteadySolver,
    available_steady_solvers,
    select_steady_solver,
)
from continuo.solve.steady import (
    directive_nodomain,
    directive_solver,
    directive_solver_options,
    evaluate_parameters,
    steady_state,
)

__all__ = [
    "simulate",
    "steady_state",
    "directive_solver",
    "directive_solver_options",
    "directive_nodomain",
    "evaluate_parameters",
    "solve_pf",
    "solve_segment",
    "Solution",
    "SolveError",
    "LinearSolver",
    "SuperluSolver",
    "KluSolver",
    "UmfpackSolver",
    "PardisoSolver",
    "SOLVERS",
    "available_solvers",
    "select_solver",
    "SteadySolver",
    "RootProblem",
    "RootResult",
    "NewtonSolver",
    "ScipyRootSolver",
    "KinsolSolver",
    "HomotopySolver",
    "AutoSolver",
    "STEADY_SOLVERS",
    "available_steady_solvers",
    "select_steady_solver",
]

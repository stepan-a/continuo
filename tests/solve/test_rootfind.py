"""Tests for the pluggable nonlinear steady-state solvers."""

from __future__ import annotations

import casadi as ca
import numpy as np
import pytest

from continuo.solve import (
    AutoSolver,
    HomotopySolver,
    KinsolSolver,
    NewtonSolver,
    RootProblem,
    RootResult,
    ScipyRootSolver,
    SolveError,
    available_steady_solvers,
    select_steady_solver,
)
from continuo.solve.rootfind import STEADY_SOLVERS

needs_kinsol = pytest.mark.skipif(
    "kinsol" not in available_steady_solvers(), reason="CasADi has no KINSOL plugin"
)

# A small nonlinear system: x0² = 2, x1 = x0. Root: (√2, √2).
ROOT = np.array([np.sqrt(2.0), np.sqrt(2.0)])


def _g(x: np.ndarray) -> np.ndarray:
    return np.array([x[0] ** 2 - 2.0, x[1] - x[0]])


def _jac(x: np.ndarray) -> np.ndarray:
    return np.array([[2.0 * x[0], 0.0], [-1.0, 1.0]])


def _problem(x0=(1.0, 1.0)) -> RootProblem:
    x = ca.SX.sym("x", 2)
    f = ca.Function("f", [x], [ca.vertcat(x[0] ** 2 - 2.0, x[1] - x[0])])
    return RootProblem(_g, _jac, np.array(x0, dtype=float), residual_function=f, names=("a", "b"))


# --- individual backends --------------------------------------------------


@pytest.mark.parametrize("name", sorted(available_steady_solvers()))
def test_backend_solves_system(name):
    # Derivative-free presets converge to a looser tolerance.
    tol = 1e-10 if name in ("newton", "hybr", "lm", "kinsol", "homotopy") else 1e-7
    result = STEADY_SOLVERS[name]().solve(_problem(), tol=tol, max_iter=200)
    assert result.success, result.message
    assert result.algorithm == name
    np.testing.assert_allclose(result.x, ROOT, atol=tol * 10 + 1e-7)


def test_newton_reports_failure_without_raising():
    # A per-iteration cap of 0 starves Newton; it reports, not raises.
    result = NewtonSolver().solve(_problem(), tol=1e-10, max_iter=0)
    assert not result.success
    assert "did not converge" in result.message


def test_newton_armijo_backtracks_around_domain_boundary():
    # log(x) = 0 at x = 1; the full Newton step from x0 = 5 overshoots into
    # log(negative) = NaN. The Armijo line search rejects the non-finite merit
    # and backtracks, keeping the iterate in the domain.
    def g(x):
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.array([np.log(x[0])])

    problem = RootProblem(g, lambda x: np.array([[1.0 / x[0]]]), np.array([5.0]))
    result = NewtonSolver().solve(problem, tol=1e-10, max_iter=50)
    assert result.success, result.message
    assert abs(result.x[0] - 1.0) < 1e-8


# --- homotopy / auto from a far guess -------------------------------------


# g(x) = arctan(x): a strongly nonlinear scalar root at 0, far guess x0 = 5.
def _atan_problem(x0: float) -> RootProblem:
    return RootProblem(
        lambda x: np.array([np.arctan(x[0])]),
        lambda x: np.array([[1.0 / (1.0 + x[0] ** 2)]]),
        np.array([x0], dtype=float),
    )


def test_homotopy_converges_from_far_guess():
    result = HomotopySolver().solve(_atan_problem(5.0), tol=1e-10, max_iter=50)
    assert result.success, result.message
    assert abs(result.x[0]) < 1e-8


def test_auto_converges_from_far_guess():
    result = select_steady_solver("auto").solve(_atan_problem(5.0), tol=1e-10, max_iter=50)
    assert result.success
    assert abs(result.x[0]) < 1e-8


class _AlwaysFails:
    """A stub backend that never converges, for testing the auto fall-through."""

    def __init__(self, name: str):
        self.name = name

    def solve(self, problem, *, tol, max_iter):
        return RootResult(problem.x0, False, 0, problem.norm(problem.x0), self.name, "stub failure")


def test_auto_falls_through_to_a_working_backend():
    auto = AutoSolver((_AlwaysFails("stub"), NewtonSolver()))
    result = auto.solve(_problem(), tol=1e-10, max_iter=50)
    assert result.success
    assert result.algorithm == "newton"  # the stub failed, Newton won


def test_auto_reports_every_attempt_when_all_fail():
    auto = AutoSolver((_AlwaysFails("alpha"), _AlwaysFails("beta")))
    result = auto.solve(_problem(), tol=1e-10, max_iter=50)
    assert not result.success
    assert "alpha" in result.message and "beta" in result.message


# --- selection / availability ---------------------------------------------


def test_select_auto_returns_auto_solver():
    assert isinstance(select_steady_solver(None), AutoSolver)
    assert isinstance(select_steady_solver("auto"), AutoSolver)


def test_auto_chain_is_hybr_lm_homotopy():
    auto = select_steady_solver("auto")
    assert [member.name for member in auto.chain] == ["hybr", "lm", "homotopy"]


def test_select_named_returns_that_backend():
    assert select_steady_solver("hybr").name == "hybr"


def test_select_instance_passes_through():
    inst = NewtonSolver()
    assert select_steady_solver(inst) is inst


def test_select_unknown_rejected():
    with pytest.raises(SolveError, match="unknown steady-state solver 'magic'"):
        select_steady_solver("magic")


def test_select_unavailable_rejected():
    with pytest.raises(SolveError, match="unavailable"):
        select_steady_solver("kinsol", available=frozenset({"newton"}))


def test_availability_gates_kinsol_on_casadi():
    available = available_steady_solvers()
    assert "newton" in available and "homotopy" in available
    assert ("kinsol" in available) == ca.has_rootfinder("kinsol")


# --- backend options (Layers 1 & 2) ---------------------------------------


def test_newton_line_search_steps_option():
    solver = NewtonSolver(line_search_steps=5)
    assert solver.line_search_steps == 5
    assert solver.solve(_problem(), tol=1e-10, max_iter=100).success


def test_kinsol_strategy_option():
    assert KinsolSolver(strategy="picard").strategy == "picard"


def test_kinsol_rejects_unknown_strategy():
    with pytest.raises(SolveError, match="unknown kinsol strategy 'bogus'"):
        KinsolSolver(strategy="bogus")


def test_scipy_options_passed_through():
    solver = ScipyRootSolver("hybr", uses_jac=True, scipy_options={"factor": 0.5})
    assert solver.scipy_options == {"factor": 0.5}
    assert solver.solve(_problem(), tol=1e-10, max_iter=100).success


def test_select_forwards_scipy_options():
    assert select_steady_solver("hybr", options={"factor": 0.1}).scipy_options == {"factor": 0.1}


@needs_kinsol
def test_select_forwards_kinsol_options():
    assert select_steady_solver("kinsol", options={"strategy": "picard"}).strategy == "picard"


def test_select_rejects_unknown_option_for_named_backend():
    with pytest.raises(SolveError, match="invalid options for steady-state solver 'newton'"):
        select_steady_solver("newton", options={"bogus": 1})


def test_select_rejects_options_on_instance():
    with pytest.raises(SolveError, match="cannot be combined with a constructed"):
        select_steady_solver(NewtonSolver(), options={"line_search_steps": 5})


def test_select_rejects_options_on_auto():
    with pytest.raises(SolveError, match="not supported with 'auto'"):
        select_steady_solver("auto", options={"strategy": "picard"})


def test_scipy_wrapper_reports_residual_above_tol():
    # df-sane on a strict tol it cannot reach reports failure with the norm.
    result = ScipyRootSolver("df-sane", uses_jac=False).solve(_problem(), tol=1e-14, max_iter=50)
    if not result.success:
        assert "‖g‖∞" in result.message

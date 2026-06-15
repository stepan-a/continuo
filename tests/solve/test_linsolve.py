"""Tests for the pluggable linear-solver interface and the SuperLU backend."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.sparse import csc_matrix

from continuo.solve import SolveError
from continuo.solve.linsolve import LinearSolver, SuperluSolver, select_solver


def random_system(n: int, seed: int) -> tuple[csc_matrix, np.ndarray]:
    """A well-conditioned sparse system ``A x = b`` (diagonally dominant)."""
    rng = np.random.default_rng(seed)
    a = rng.standard_normal((n, n)) * (rng.random((n, n)) < 0.4)
    a += np.diag(np.abs(a).sum(axis=1) + 1.0)  # strict diagonal dominance
    b = rng.standard_normal(n)
    return csc_matrix(a), b


def test_superlu_satisfies_the_protocol():
    assert isinstance(SuperluSolver(), LinearSolver)


def test_superlu_solve_matches_dense():
    solver = SuperluSolver()
    a, b = random_system(12, seed=0)
    sym = solver.analyze(a)
    num = solver.factor(a, sym)
    x = solver.solve(num, b)
    np.testing.assert_allclose(a @ x, b, atol=1e-10)
    np.testing.assert_allclose(x, np.linalg.solve(a.toarray(), b), atol=1e-10)


def test_refactor_reuses_ordering_and_stays_correct():
    # The pattern is fixed at analyze; refactor must solve a *different*
    # numeric matrix with that same ordering.
    solver = SuperluSolver()
    a0, _ = random_system(10, seed=1)
    sym = solver.analyze(a0)

    a1 = a0.copy()
    a1.data = a1.data * 1.5 + 0.1  # same pattern, new values
    b = np.arange(1.0, 11.0)
    num = solver.factor(a0, sym)
    num = solver.refactor(a1, sym, num)
    np.testing.assert_allclose(a1 @ solver.solve(num, b), b, atol=1e-10)


def test_rcond_is_none_for_superlu():
    solver = SuperluSolver()
    a, _ = random_system(5, seed=2)
    assert solver.rcond(solver.factor(a, solver.analyze(a))) is None


def test_solve_accepts_a_list_rhs():
    solver = SuperluSolver()
    a, _ = random_system(4, seed=3)
    num = solver.factor(a, solver.analyze(a))
    x = solver.solve(num, [1.0, 2.0, 3.0, 4.0])
    np.testing.assert_allclose(a @ x, [1.0, 2.0, 3.0, 4.0], atol=1e-10)


def test_name():
    assert SuperluSolver().name == "superlu"


# --- select_solver --------------------------------------------------------


def test_select_default_and_auto_resolve_to_superlu():
    assert isinstance(select_solver(None), SuperluSolver)
    assert isinstance(select_solver("auto"), SuperluSolver)


def test_select_named_preset():
    assert select_solver("superlu").name == "superlu"


def test_select_passes_instances_through_untouched():
    instance = SuperluSolver()
    assert select_solver(instance) is instance


def test_select_unknown_preset_rejected():
    with pytest.raises(SolveError, match="unknown linear solver"):
        select_solver("nope")


def test_select_unavailable_preset_rejected():
    with pytest.raises(SolveError, match="unavailable"):
        select_solver("superlu", available=frozenset())

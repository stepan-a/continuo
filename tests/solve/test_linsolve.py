"""Tests for the pluggable linear-solver interface and its backends."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.sparse import csc_matrix

from continuo.solve import SolveError, _klu, available_solvers
from continuo.solve.linsolve import KluSolver, LinearSolver, SuperluSolver, select_solver

requires_klu = pytest.mark.skipif(not _klu.is_available(), reason="libklu.so not available")


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


# --- KLU backend ----------------------------------------------------------


@requires_klu
def test_klu_satisfies_the_protocol():
    assert isinstance(KluSolver(), LinearSolver)


@requires_klu
def test_klu_is_advertised_when_the_library_is_present():
    assert {"klu", "klu-nobtf"} <= available_solvers()
    assert select_solver("klu").name == "klu"
    assert select_solver("klu-nobtf").name == "klu-nobtf"


@requires_klu
@pytest.mark.parametrize("btf", [True, False])
def test_klu_solve_matches_dense(btf):
    solver = KluSolver(btf=btf)
    a, b = random_system(12, seed=0)
    num = solver.factor(a, solver.analyze(a))
    x = solver.solve(num, b)
    np.testing.assert_allclose(x, np.linalg.solve(a.toarray(), b), atol=1e-10)


@requires_klu
def test_klu_matches_superlu_on_the_same_system():
    a, b = random_system(20, seed=4)
    sym = KluSolver().analyze(a)
    klu = KluSolver().solve(KluSolver().factor(a, sym), b)
    superlu = SuperluSolver().solve(SuperluSolver().factor(a, SuperluSolver().analyze(a)), b)
    np.testing.assert_allclose(klu, superlu, atol=1e-10)


@requires_klu
def test_klu_refactor_reuses_the_symbolic_analysis():
    solver = KluSolver()
    a0, _ = random_system(10, seed=1)
    sym = solver.analyze(a0)
    a1 = a0.copy()
    a1.data = a1.data * 1.5 + 0.1  # same pattern, new values
    b = np.arange(1.0, 11.0)
    num = solver.refactor(a1, sym, solver.factor(a0, sym))
    np.testing.assert_allclose(a1 @ solver.solve(num, b), b, atol=1e-10)


@requires_klu
def test_klu_rcond_is_a_finite_estimate():
    solver = KluSolver()
    a, _ = random_system(8, seed=2)
    rc = solver.rcond(solver.factor(a, solver.analyze(a)))
    assert rc is not None and 0.0 < rc <= 1.0


@requires_klu
def test_klu_rejects_a_structurally_singular_pattern():
    # A 4x4 with an all-zero column 3 is structurally rank-deficient; BTF's
    # maximum-transversal sees it at analyse time.
    a = csc_matrix(np.diag([1.0, 1.0, 1.0, 0.0]))
    with pytest.raises(SolveError, match="structurally singular"):
        KluSolver().analyze(a)


@requires_klu
def test_klu_names_reflect_btf():
    assert KluSolver(btf=True).name == "klu"
    assert KluSolver(btf=False).name == "klu-nobtf"


def test_klu_rejects_unknown_ordering():
    with pytest.raises(SolveError, match="unknown KLU ordering"):
        KluSolver(ordering="metis")

"""Pluggable linear-solver interface for the Newton core.

Each Newton step solves ``J ΔX = -G``. The sparsity *pattern* of the
stacked Jacobian is constant across Newton iterations (and, at a fixed
grid, across segments), so the symbolic work — fill-reducing ordering and
symbolic factorisation — can be done *once* and the numeric factorisation
refreshed cheaply at each step. The :class:`LinearSolver` protocol exposes
that structure as four phases:

- :meth:`~LinearSolver.analyze` — symbolic, pattern-only, hoisted out of
  the Newton loop;
- :meth:`~LinearSolver.factor` — full numeric factorisation with pivoting;
- :meth:`~LinearSolver.refactor` — cheap numeric refresh reusing the pivot
  order (falls back to :meth:`factor` when a backend cannot reuse it);
- :meth:`~LinearSolver.solve` — triangular solves for a right-hand side.

:meth:`~LinearSolver.rcond` feeds the Newton guard-rail: when a reused
factorisation degrades, the driver falls back to a fresh :meth:`factor`.

:class:`SuperluSolver` is the always-available backend — SciPy is a hard
dependency of continuo. It captures SciPy's COLAMD column ordering once in
:meth:`analyze` and refactorises with that fixed ordering thereafter.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

import numpy as np
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import splu

from continuo.solve import _klu
from continuo.solve.errors import SolveError

__all__ = [
    "LinearSolver",
    "SuperluSolver",
    "KluSolver",
    "SOLVERS",
    "available_solvers",
    "select_solver",
]


@runtime_checkable
class LinearSolver(Protocol):
    """A pluggable sparse linear solver exposing the analyze/factor/refactor/solve phases."""

    name: str

    def analyze(self, a0: csc_matrix) -> Any:
        """Symbolic phase: fill-reducing ordering / symbolic factorisation.

        Depends only on the *pattern* of ``a0`` (constant over the solve),
        so it is computed once and reused across Newton iterations. ``a0``
        is a numeric matrix sampled at the initial iterate; only its
        sparsity pattern is consulted.
        """
        ...

    def factor(self, a: csc_matrix, sym: Any) -> Any:
        """Full numeric factorisation with pivoting (first step / guard-rail)."""
        ...

    def refactor(self, a: csc_matrix, sym: Any, num: Any) -> Any:
        """Cheap numeric refactorisation reusing the pivot order.

        Backends without genuine symbolic reuse fall back to :meth:`factor`.
        """
        ...

    def solve(self, num: Any, b: np.ndarray) -> np.ndarray:
        """Solve ``A x = b`` using the numeric factorisation ``num``."""
        ...

    def rcond(self, num: Any) -> float | None:
        """Reciprocal-condition estimate for the guard-rail, or ``None`` if unavailable."""
        ...


class _SuperluSym:
    """SuperLU symbolic data: the COLAMD column permutation, reused every step."""

    __slots__ = ("perm_c",)

    def __init__(self, perm_c: np.ndarray):
        self.perm_c = perm_c


class SuperluSolver:
    """SciPy SuperLU backend: the always-available fallback.

    SciPy chooses a COLAMD column ordering inside ``splu``; we capture it
    once in :meth:`analyze` and refactorise on the column-permuted matrix
    with ``permc_spec="NATURAL"`` so the ordering is not recomputed at each
    step. SciPy exposes no symbolic-only reuse, so :meth:`refactor` is a
    full numeric factorisation with the fixed ordering, and :meth:`rcond`
    returns ``None`` (no cheap estimate available).
    """

    name = "superlu"

    def analyze(self, a0: csc_matrix) -> _SuperluSym:
        # COLAMD ordering from the first numeric matrix; it depends only on
        # the (constant) pattern, so it is valid for every later step.
        return _SuperluSym(splu(a0).perm_c)

    def factor(self, a: csc_matrix, sym: _SuperluSym) -> tuple[Any, np.ndarray]:
        perm_c = sym.perm_c
        lu = splu(a[:, perm_c].tocsc(), permc_spec="NATURAL")
        return lu, perm_c

    def refactor(self, a: csc_matrix, sym: _SuperluSym, num: Any) -> tuple[Any, np.ndarray]:
        # No symbolic-only reuse in SciPy: a refactor is a fixed-ordering factor.
        return self.factor(a, sym)

    def solve(self, num: tuple[Any, np.ndarray], b: np.ndarray) -> np.ndarray:
        lu, perm_c = num
        y = lu.solve(np.asarray(b, dtype=float))
        x = np.empty_like(y)
        x[perm_c] = y  # undo the column permutation: x[perm_c[j]] = y[j]
        return x

    def rcond(self, num: Any) -> float | None:
        return None


class _KluSym:
    """KLU symbolic data: the native analysis plus the (constant) CSC pattern."""

    __slots__ = ("symbolic",)

    def __init__(self, symbolic: Any):
        self.symbolic = symbolic


class KluSolver:
    """SuiteSparse KLU backend (``libklu.so``), the recommended one-step solver.

    KLU pre-orders the matrix into block triangular form (BTF) and reuses
    that symbolic analysis across numeric refactorisations, so the stacked
    Jacobian of a one-step scheme — which is block-triangular — is solved by
    block back-substitution. ``btf`` is a *parameter* applied at analyse
    time, not a separate backend: ``btf=False`` turns KLU into a plain
    sparse LU (useful for multi-step schemes where BTF is pure overhead).
    ``ordering`` picks the per-block fill-reducing ordering (``"amd"`` or
    ``"colamd"``); ``scale`` is KLU's row scaling (kept at its default when
    ``None``).

    Requires ``libklu.so`` at runtime; :func:`available_solvers` gates the
    preset on its presence and the caller falls back to SuperLU otherwise.
    """

    def __init__(self, *, btf: bool = True, ordering: str = "amd", scale: int | None = None):
        if ordering not in _klu.ORDERING:
            raise SolveError(
                f"unknown KLU ordering {ordering!r}; expected one of {sorted(_klu.ORDERING)}"
            )
        self.btf = btf
        self.ordering = ordering
        self.scale = scale
        self.name = "klu" if btf else "klu-nobtf"

    def analyze(self, a0: csc_matrix) -> _KluSym:
        ap, ai, _ = _csc_arrays(a0)
        common = _klu.make_common(btf=self.btf, ordering=self.ordering, scale=self.scale)
        symbolic = _klu.analyze(ap, ai, common)
        rank = symbolic.structural_rank
        if rank not in (-1, symbolic.n):  # -1 means "not computed" (btf=False)
            raise SolveError(
                f"structurally singular Jacobian: KLU structural rank {rank} of {symbolic.n}"
            )
        return _KluSym(symbolic)

    def factor(self, a: csc_matrix, sym: _KluSym) -> Any:
        return _klu.factor(_csc_arrays(a)[2], sym.symbolic)

    def refactor(self, a: csc_matrix, sym: _KluSym, num: Any) -> Any:
        return _klu.refactor(_csc_arrays(a)[2], sym.symbolic, num)

    def solve(self, num: Any, b: np.ndarray) -> np.ndarray:
        return _klu.solve(num, np.asarray(b, dtype=float))

    def rcond(self, num: Any) -> float | None:
        return num.rcond


def _csc_arrays(a: csc_matrix) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Canonical CSC ``(indptr, indices, data)`` as int32 / int32 / float64 for KLU."""
    a = a.tocsc()
    a.sum_duplicates()
    a.sort_indices()
    return (
        a.indptr.astype(np.int32, copy=False),
        a.indices.astype(np.int32, copy=False),
        a.data.astype(np.float64, copy=False),
    )


# ---------------------------------------------------------------------------
# registry and selection
# ---------------------------------------------------------------------------

# Preset name -> factory. Optional backends (umfpack, pardiso) register here
# as they are added; ``superlu`` is always present.
SOLVERS: dict[str, Callable[[], LinearSolver]] = {
    "superlu": lambda: SuperluSolver(),
    "klu": lambda: KluSolver(btf=True),
    "klu-nobtf": lambda: KluSolver(btf=False),
}


def available_solvers() -> frozenset[str]:
    """Preset names whose backend can actually run in this environment.

    SciPy is a hard dependency, so ``superlu`` is always available; ``klu``
    needs ``libklu.so`` at runtime and is gated on its presence. Other
    optional backends probe their packages and join the set in later commits.
    """
    names = {"superlu"}
    if _klu.is_available():
        names |= {"klu", "klu-nobtf"}
    return frozenset(names)


def select_solver(
    requested: str | LinearSolver | None,
    available: frozenset[str] | None = None,
) -> LinearSolver:
    """Resolve a user request into a concrete :class:`LinearSolver`.

    ``requested`` is a preset name, an already-built solver instance (passed
    through untouched for fine control), or ``None`` / ``"auto"`` to let
    continuo choose. Unknown or unavailable presets raise :class:`SolveError`.
    """
    if isinstance(requested, LinearSolver):
        return requested
    available = available_solvers() if available is None else available
    name = requested or "auto"
    if name == "auto":
        # Only one backend today; stencil-aware routing (one-step -> klu,
        # multi-step -> banded) lands with those backends.
        name = "superlu"
    if name not in SOLVERS:
        raise SolveError(f"unknown linear solver {name!r}; presets: {sorted(SOLVERS)}")
    if name not in available:
        raise SolveError(
            f"linear solver {name!r} is unavailable here (available: {sorted(available)})"
        )
    return SOLVERS[name]()

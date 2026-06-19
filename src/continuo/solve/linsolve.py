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

import contextlib
import importlib.util
import logging
from collections.abc import Callable, Iterator
from typing import Any, Protocol, runtime_checkable

import numpy as np
from scipy.sparse import csc_matrix, csr_matrix
from scipy.sparse.linalg import splu

from continuo.solve import _klu
from continuo.solve.errors import SolveError

logger = logging.getLogger(__name__)

__all__ = [
    "LinearSolver",
    "SuperluSolver",
    "KluSolver",
    "UmfpackSolver",
    "PardisoSolver",
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

    def nnz(self, num: Any) -> int | None:
        """Factorisation fill ``nnz(L) + nnz(U)`` for diagnostics, or ``None`` if unavailable."""
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

    def nnz(self, num: tuple[Any, np.ndarray]) -> int:
        lu, _ = num
        return int(lu.L.nnz + lu.U.nnz)


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
        with _as_solve_error():
            common = _klu.make_common(btf=self.btf, ordering=self.ordering, scale=self.scale)
            symbolic = _klu.analyze(ap, ai, common)
        rank = symbolic.structural_rank
        if rank not in (-1, symbolic.n):  # -1 means "not computed" (btf=False)
            raise SolveError(
                f"structurally singular Jacobian: KLU structural rank {rank} of {symbolic.n}"
            )
        return _KluSym(symbolic)

    def factor(self, a: csc_matrix, sym: _KluSym) -> Any:
        with _as_solve_error():
            return _klu.factor(_csc_arrays(a)[2], sym.symbolic)

    def refactor(self, a: csc_matrix, sym: _KluSym, num: Any) -> Any:
        with _as_solve_error():
            return _klu.refactor(_csc_arrays(a)[2], sym.symbolic, num)

    def solve(self, num: Any, b: np.ndarray) -> np.ndarray:
        with _as_solve_error():
            return _klu.solve(num, np.asarray(b, dtype=float))

    def rcond(self, num: Any) -> float | None:
        return num.rcond

    def nnz(self, num: Any) -> int | None:
        return None  # KLU does not expose the factor fill here


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


@contextlib.contextmanager
def _as_solve_error() -> Iterator[None]:
    """Translate a low-level :class:`_klu.KluError` into a :class:`SolveError`.

    This lets the Newton driver treat a failed KLU refactor (e.g. a stale-pivot
    zero) uniformly and fall back to a full factor.
    """
    try:
        yield
    except _klu.KluError as exc:
        raise SolveError(str(exc)) from exc


class _UmfpackSym:
    """UMFPACK symbolic data: the context holding the reusable symbolic analysis."""

    __slots__ = ("ctx",)

    def __init__(self, ctx: Any):
        self.ctx = ctx


class _UmfpackNum:
    """UMFPACK numeric data: the factorised context, its matrix, rcond and fill."""

    __slots__ = ("ctx", "a", "rcond", "fill")

    def __init__(self, ctx: Any, a: csc_matrix, rcond: float | None, fill: int | None):
        self.ctx = ctx
        self.a = a
        self.rcond = rcond
        self.fill = fill


class UmfpackSolver:
    """SuiteSparse UMFPACK backend via ``scikit-umfpack`` (optional extra).

    UMFPACK separates the symbolic analysis from the numeric factorisation
    cleanly, so :meth:`analyze` runs it once and :meth:`refactor` re-runs only
    the numeric phase. Its numeric phase is slower than SuperLU/KLU, so this
    backend is offered for completeness rather than as a default. Requires the
    ``umfpack`` extra (``scikit-umfpack``); uses the int32 ``"di"`` family.
    """

    name = "umfpack"

    def analyze(self, a0: csc_matrix) -> _UmfpackSym:
        from scikits import umfpack

        ctx = umfpack.UmfpackContext("di")
        ctx.symbolic(_umfpack_matrix(a0))
        return _UmfpackSym(ctx)

    def factor(self, a: csc_matrix, sym: _UmfpackSym) -> _UmfpackNum:
        from scikits import umfpack

        m = _umfpack_matrix(a)
        sym.ctx.numeric(m)  # reuses the stored symbolic analysis
        info = sym.ctx.info
        rcond = float(info[umfpack.UMFPACK_RCOND])
        fill = int(info[umfpack.UMFPACK_LNZ] + info[umfpack.UMFPACK_UNZ])
        return _UmfpackNum(sym.ctx, m, rcond, fill)

    def refactor(self, a: csc_matrix, sym: _UmfpackSym, num: _UmfpackNum) -> _UmfpackNum:
        return self.factor(a, sym)  # the numeric phase already reuses the symbolic

    def solve(self, num: _UmfpackNum, b: np.ndarray) -> np.ndarray:
        from scikits import umfpack

        return num.ctx.solve(umfpack.UMFPACK_A, num.a, np.asarray(b, dtype=float))

    def rcond(self, num: _UmfpackNum) -> float | None:
        return num.rcond

    def nnz(self, num: _UmfpackNum) -> int | None:
        return num.fill


class _PardisoNum:
    """PARDISO numeric data: the factorised solver and its CSR matrix."""

    __slots__ = ("ps", "a")

    def __init__(self, ps: Any, a: csr_matrix):
        self.ps = ps
        self.a = a


class PardisoSolver:
    """Intel MKL PARDISO backend via ``pypardiso`` (optional extra).

    PARDISO is multithreaded (MKL) and competitive on large problems, but its
    analysis is expensive and it has no BTF, so it is offered for large /
    multi-core runs rather than as a default. Its Python API does not expose a
    symbolic-only phase, so :meth:`analyze` is a no-op and each :meth:`factor`
    runs analysis + numeric factorisation. Requires the ``pardiso`` extra
    (``pypardiso``); consumes CSR int32 matrices.
    """

    name = "pardiso"

    def analyze(self, a0: csc_matrix) -> Any:
        from pypardiso import PyPardisoSolver

        return PyPardisoSolver()

    def factor(self, a: csc_matrix, sym: Any) -> _PardisoNum:
        m = _pardiso_matrix(a)
        sym.factorize(m)
        return _PardisoNum(sym, m)

    def refactor(self, a: csc_matrix, sym: Any, num: _PardisoNum) -> _PardisoNum:
        return self.factor(a, sym)

    def solve(self, num: _PardisoNum, b: np.ndarray) -> np.ndarray:
        return num.ps.solve(num.a, np.asarray(b, dtype=float))

    def rcond(self, num: _PardisoNum) -> float | None:
        return None

    def nnz(self, num: _PardisoNum) -> int | None:
        return None  # pypardiso does not expose the factor fill


def _umfpack_matrix(a: csc_matrix) -> csc_matrix:
    """Canonical CSC, float64 data and int32 indices, isolated from the caller."""
    a = a.tocsc()
    m = csc_matrix(
        (a.data.astype(np.float64), a.indices.astype(np.int32), a.indptr.astype(np.int32)),
        shape=a.shape,
    )
    m.sum_duplicates()
    m.sort_indices()
    return m


def _pardiso_matrix(a: csc_matrix) -> csr_matrix:
    """Canonical CSR, float64 data and int32 indices, as PARDISO expects."""
    a = a.tocsr()
    m = csr_matrix(
        (a.data.astype(np.float64), a.indices.astype(np.int32), a.indptr.astype(np.int32)),
        shape=a.shape,
    )
    m.sum_duplicates()
    m.sort_indices()
    return m


# ---------------------------------------------------------------------------
# registry and selection
# ---------------------------------------------------------------------------

# Preset name -> factory. ``superlu`` is always present; the others are gated
# by availability (see :func:`available_solvers`).
SOLVERS: dict[str, Callable[[], LinearSolver]] = {
    "superlu": lambda: SuperluSolver(),
    "klu": lambda: KluSolver(btf=True),
    "klu-nobtf": lambda: KluSolver(btf=False),
    "umfpack": lambda: UmfpackSolver(),
    "pardiso": lambda: PardisoSolver(),
}

_module_present: dict[str, bool] = {}


def _has_module(name: str) -> bool:
    """Whether an importable module is present, without importing it (cached).

    ``find_spec`` locates the module without executing it, so probing for an
    optional backend does not pay its (possibly heavy, e.g. MKL) import cost.
    """
    if name not in _module_present:
        try:
            _module_present[name] = importlib.util.find_spec(name) is not None
        except (ImportError, ValueError):
            _module_present[name] = False
    return _module_present[name]


def available_solvers() -> frozenset[str]:
    """Preset names whose backend can actually run in this environment.

    SciPy is a hard dependency, so ``superlu`` is always available. ``klu``
    needs ``libklu.so`` at runtime; ``umfpack`` and ``pardiso`` need their
    optional packages (``scikit-umfpack`` / ``pypardiso``).
    """
    names = {"superlu"}
    if _klu.is_available():
        names |= {"klu", "klu-nobtf"}
    if _has_module("scikits.umfpack"):
        names.add("umfpack")
    if _has_module("pypardiso"):
        names.add("pardiso")
    return frozenset(names)


_warned_no_klu = False


def _warn_klu_missing() -> None:
    global _warned_no_klu
    if not _warned_no_klu:
        _warned_no_klu = True
        logger.warning(
            "KLU backend unavailable (libklu.so not found); falling back to SuperLU. "
            "Install SuiteSparse (Debian: libsuitesparse-dev) for the faster one-step solver."
        )


def _auto_pick(stencil: str, available: frozenset[str]) -> str:
    """Choose a backend for ``solver="auto"`` from the scheme's coupling stencil."""
    if stencil == "one-step":  # block-triangular stacked Jacobian -> KLU + BTF
        if "klu" in available:
            return "klu"
        _warn_klu_missing()
        return "superlu"
    # multi-step (banded Jacobian): prefer a banded solver, then KLU without the
    # (useless) BTF, then SuperLU. The banded backend lands with multi-step schemes.
    for name in ("banded", "klu-nobtf"):
        if name in available:
            return name
    return "superlu"


def select_solver(
    requested: str | LinearSolver | None,
    available: frozenset[str] | None = None,
    *,
    stencil: str = "one-step",
) -> LinearSolver:
    """Resolve a user request into a concrete :class:`LinearSolver`.

    ``requested`` is a preset name, an already-built solver instance (passed
    through untouched for fine control), or ``None`` / ``"auto"`` to let
    continuo choose by the scheme's coupling ``stencil`` (``"one-step"`` routes
    to KLU when available, falling back to SuperLU). Unknown or unavailable
    presets raise :class:`SolveError`.
    """
    if isinstance(requested, LinearSolver):
        return requested
    available = available_solvers() if available is None else available
    name = requested or "auto"
    if name == "auto":
        name = _auto_pick(stencil, available)
    if name not in SOLVERS:
        raise SolveError(f"unknown linear solver {name!r}; presets: {sorted(SOLVERS)}")
    if name not in available:
        raise SolveError(
            f"linear solver {name!r} is unavailable here (available: {sorted(available)})"
        )
    return SOLVERS[name]()

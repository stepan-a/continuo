"""ctypes binding to SuiteSparse KLU (``libklu.so``).

KLU factorises a sparse matrix as ``A = L·U`` after a BTF (block
triangular form) pre-ordering, so block-triangular stacked Jacobians — the
one-step collocation schemes — are solved by block back-substitution. The
symbolic phase (ordering + BTF) depends only on the pattern and is reused
across numeric refactorisations.

The library is loaded lazily, so importing continuo never requires the
native library: :func:`is_available` reports whether the backend can run,
and the caller falls back to SuperLU when it cannot. KLU consumes CSC
matrices with ``int32`` index arrays (``Ap``, ``Ai``) and ``float64``
values (``Ax``); the int32 ``klu_*`` entry points are bound here.

The :class:`KluCommon` layout mirrors ``klu_common`` from
``suitesparse/klu.h`` field-for-field — it carries both the control
parameters (``btf``, ``ordering``, ``scale``) and the statistics read back
after each phase (``status``, ``structural_rank``, ``rcond``).
"""

from __future__ import annotations

import ctypes
import ctypes.util
import weakref
from ctypes import POINTER, Structure, byref, c_double, c_int, c_int32, c_size_t, c_void_p

import numpy as np

__all__ = ["is_available", "KluError", "make_common", "analyze", "factor", "refactor", "solve"]

KLU_OK = 0
ORDERING = {"amd": 0, "colamd": 1}


class KluError(RuntimeError):
    """A KLU call returned a non-OK status."""


class KluCommon(Structure):
    """Mirror of ``klu_common`` (suitesparse/klu.h): control parameters + statistics."""

    _fields_ = [
        # parameters
        ("tol", c_double),
        ("memgrow", c_double),
        ("initmem_amd", c_double),
        ("initmem", c_double),
        ("maxwork", c_double),
        ("btf", c_int),
        ("ordering", c_int),
        ("scale", c_int),
        ("user_order", c_void_p),  # function pointer, unused here
        ("user_data", c_void_p),
        ("halt_if_singular", c_int),
        # statistics
        ("status", c_int),
        ("nrealloc", c_int),
        ("structural_rank", c_int32),
        ("numerical_rank", c_int32),
        ("singular_col", c_int32),
        ("noffdiag", c_int32),
        ("flops", c_double),
        ("rcond", c_double),
        ("condest", c_double),
        ("rgrowth", c_double),
        ("work", c_double),
        ("memusage", c_size_t),
        ("mempeak", c_size_t),
    ]


_I32 = np.ctypeslib.ndpointer(dtype=np.int32, flags="C_CONTIGUOUS")
_F64 = np.ctypeslib.ndpointer(dtype=np.float64, flags="C_CONTIGUOUS")

_lib: ctypes.CDLL | None = None
_tried = False


def _candidates():
    yield "libklu.so"
    yield "libklu.so.2"
    found = ctypes.util.find_library("klu")
    if found:
        yield found


def _bind(lib: ctypes.CDLL) -> None:
    common = POINTER(KluCommon)
    lib.klu_defaults.argtypes = [common]
    lib.klu_defaults.restype = c_int
    lib.klu_analyze.argtypes = [c_int32, _I32, _I32, common]
    lib.klu_analyze.restype = c_void_p
    lib.klu_factor.argtypes = [_I32, _I32, _F64, c_void_p, common]
    lib.klu_factor.restype = c_void_p
    lib.klu_refactor.argtypes = [_I32, _I32, _F64, c_void_p, c_void_p, common]
    lib.klu_refactor.restype = c_int
    lib.klu_solve.argtypes = [c_void_p, c_void_p, c_int32, c_int32, _F64, common]
    lib.klu_solve.restype = c_int
    lib.klu_rcond.argtypes = [c_void_p, c_void_p, common]
    lib.klu_rcond.restype = c_int
    lib.klu_free_symbolic.argtypes = [POINTER(c_void_p), common]
    lib.klu_free_symbolic.restype = c_int
    lib.klu_free_numeric.argtypes = [POINTER(c_void_p), common]
    lib.klu_free_numeric.restype = c_int


def _load() -> ctypes.CDLL | None:
    global _lib, _tried
    if _tried:
        return _lib
    _tried = True
    for name in _candidates():
        try:
            lib = ctypes.CDLL(name)
        except OSError:
            continue
        _bind(lib)
        _lib = lib
        break
    return _lib


def is_available() -> bool:
    """Whether ``libklu.so`` could be loaded in this environment."""
    return _load() is not None


def _free_symbolic(lib: ctypes.CDLL, ptr: c_void_p, common: KluCommon) -> None:
    if ptr:
        lib.klu_free_symbolic(byref(ptr), byref(common))


def _free_numeric(lib: ctypes.CDLL, ptr: c_void_p, common: KluCommon) -> None:
    if ptr:
        lib.klu_free_numeric(byref(ptr), byref(common))


class Symbolic:
    """Owns a ``klu_symbolic*`` and the ``Common`` it was built with.

    The symbolic factorisation depends only on the pattern (``ap``, ``ai``),
    which is kept here so each numeric (re)factorisation re-feeds the exact
    same structure. Freed automatically when garbage-collected.
    """

    def __init__(self, ptr: int, common: KluCommon, ap: np.ndarray, ai: np.ndarray):
        self.ptr = c_void_p(ptr)
        self.common = common
        self.ap = ap
        self.ai = ai
        self.n = ap.shape[0] - 1
        self.structural_rank = int(common.structural_rank)
        self._finalize = weakref.finalize(self, _free_symbolic, _load(), self.ptr, common)


class Numeric:
    """Owns a ``klu_numeric*``; carries its reciprocal-condition estimate."""

    def __init__(self, ptr: int, symbolic: Symbolic):
        self.ptr = c_void_p(ptr)
        self.symbolic = symbolic
        self.rcond: float | None = None
        self._finalize = weakref.finalize(self, _free_numeric, _load(), self.ptr, symbolic.common)


def make_common(*, btf: bool, ordering: str, scale: int | None) -> KluCommon:
    """A ``klu_common`` initialised to defaults with the chosen options applied."""
    lib = _load()
    if lib is None:
        raise KluError("libklu.so is not available")
    common = KluCommon()
    lib.klu_defaults(byref(common))
    common.btf = 1 if btf else 0
    common.ordering = ORDERING[ordering]
    if scale is not None:
        common.scale = scale
    return common


def analyze(ap: np.ndarray, ai: np.ndarray, common: KluCommon) -> Symbolic:
    """Symbolic phase: BTF + fill-reducing ordering. ``ap``/``ai`` are CSC int32."""
    lib = _load()
    n = ap.shape[0] - 1
    ptr = lib.klu_analyze(n, ap, ai, byref(common))
    if not ptr or common.status != KLU_OK:
        raise KluError(f"klu_analyze failed (status {common.status})")
    return Symbolic(ptr, common, ap, ai)


def factor(ax: np.ndarray, sym: Symbolic) -> Numeric:
    """Full numeric factorisation with partial pivoting."""
    lib = _load()
    common = sym.common
    ptr = lib.klu_factor(sym.ap, sym.ai, ax, sym.ptr, byref(common))
    if not ptr or common.status != KLU_OK:
        raise KluError(f"klu_factor failed (status {common.status})")
    num = Numeric(ptr, sym)
    num.rcond = _rcond(num)
    return num


def refactor(ax: np.ndarray, sym: Symbolic, num: Numeric) -> Numeric:
    """Cheap numeric refactorisation reusing the pivot order from :func:`factor`."""
    lib = _load()
    common = sym.common
    ok = lib.klu_refactor(sym.ap, sym.ai, ax, sym.ptr, num.ptr, byref(common))
    if not ok or common.status != KLU_OK:
        raise KluError(f"klu_refactor failed (status {common.status})")
    num.rcond = _rcond(num)
    return num


def solve(num: Numeric, b: np.ndarray) -> np.ndarray:
    """Solve ``A x = b`` in place over a copy of ``b`` (single right-hand side)."""
    lib = _load()
    sym = num.symbolic
    common = sym.common
    x = np.array(b, dtype=np.float64, copy=True)
    ok = lib.klu_solve(sym.ptr, num.ptr, sym.n, 1, x, byref(common))
    if not ok or common.status != KLU_OK:
        raise KluError(f"klu_solve failed (status {common.status})")
    return x


def _rcond(num: Numeric) -> float | None:
    lib = _load()
    sym = num.symbolic
    common = sym.common
    ok = lib.klu_rcond(sym.ptr, num.ptr, byref(common))
    return float(common.rcond) if ok and common.status == KLU_OK else None

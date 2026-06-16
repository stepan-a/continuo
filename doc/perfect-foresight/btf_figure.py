#!/usr/bin/env python3
"""Generate the BTF/fill figure for the slides: the real stacked Jacobian of an
example model, and the L+U factors produced by SuperLU, KLU without BTF, and
KLU with BTF.

The Jacobian is captured by spying on a SuperLU solve of the rbc model on a
small grid. The SuperLU factors come from ``splu`` (COLAMD); the KLU factors are
read straight out of KLU via ``klu_extract`` (with the block boundaries ``R``
from ``klu_symbolic``), so every panel is the actual factorisation the backend
computes. BTF roughly halves KLU's fill; without it KLU fills even more than
SuperLU. Produces ``btf_figure.pdf``.

    python doc/perfect-foresight/btf_figure.py
"""

from __future__ import annotations

import ctypes
from ctypes import POINTER, byref, c_double, c_int32
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import splu

import continuo
from continuo.solve import _klu
from continuo.solve.linsolve import KluSolver, SuperluSolver

HERE = Path(__file__).resolve().parent
RBC = HERE.parent.parent / "examples" / "rbc" / "rbc.mod"
DARKBLUE, DARKGREEN = "#003366", "#006633"


class KluSymbolic(ctypes.Structure):
    """Mirror of KLU's ``klu_symbolic`` — P, Q, R, nblocks, nzoff."""

    _fields_ = [
        ("symmetry", c_double),
        ("est_flops", c_double),
        ("lnz", c_double),
        ("unz", c_double),
        ("Lnz", POINTER(c_double)),
        ("n", c_int32),
        ("nz", c_int32),
        ("P", POINTER(c_int32)),
        ("Q", POINTER(c_int32)),
        ("R", POINTER(c_int32)),
        ("nzoff", c_int32),
        ("nblocks", c_int32),
        ("maxblock", c_int32),
        ("ordering", c_int32),
        ("do_btf", c_int32),
        ("structural_rank", c_int32),
    ]


class KluNumericHead(ctypes.Structure):
    """The first fields of ``klu_numeric`` — enough to read the factor sizes."""

    _fields_ = [
        ("n", c_int32),
        ("nblocks", c_int32),
        ("lnz", c_int32),
        ("unz", c_int32),
    ]


def stacked_jacobian(horizon: float, intervals: int):
    """The real stacked Jacobian of rbc on a small grid (captured from a solve)."""

    class Capture(SuperluSolver):
        def __init__(self):
            self.mats: list = []

        def factor(self, a, sym):
            self.mats.append(a.copy())
            return super().factor(a, sym)

    cap = Capture()
    # Pass both horizon and intervals to override the model's simulate command.
    continuo.parse(RBC).simul(horizon=horizon, intervals=intervals, solver=cap)
    return cap.mats[-1].tocsc()


def superlu_factors(a):
    """SuperLU's combined ``L + U`` factors (COLAMD ordering) and their nnz.

    The count is the nnz of the superimposed pattern (the shared unit diagonal
    once), so it matches the markers in the spy plot.
    """
    lu = splu(a, permc_spec="COLAMD")
    lpu = (lu.L + lu.U).tocsc()
    lpu.eliminate_zeros()
    return lpu, lpu.nnz


def klu_factors(a, btf=True):
    """KLU's combined ``L + U (+ F)`` factors (read via klu_extract), blocks, nnz.

    With ``btf=False`` KLU factorises the whole matrix as one global LU (one
    block, no off-diagonal ``F``).
    """
    lib = _klu._load()
    if lib is None:
        raise SystemExit("libklu.so not available")
    lib.klu_extract.restype = ctypes.c_int

    solver = KluSolver(btf=btf)
    sym = solver.analyze(a)
    num = solver.factor(a, sym)
    sptr, nptr = sym.symbolic.ptr, num.ptr
    s = ctypes.cast(sptr, POINTER(KluSymbolic)).contents
    h = ctypes.cast(nptr, POINTER(KluNumericHead)).contents
    n, nblocks, nzoff, lnz, unz = s.n, s.nblocks, s.nzoff, h.lnz, h.unz

    lp, li, lx = (c_int32 * (n + 1))(), (c_int32 * lnz)(), (c_double * lnz)()
    up, ui, ux = (c_int32 * (n + 1))(), (c_int32 * unz)(), (c_double * unz)()
    fp, fi, fx = (c_int32 * (n + 1))(), (c_int32 * nzoff)(), (c_double * nzoff)()
    pp, qq, rs = (c_int32 * n)(), (c_int32 * n)(), (c_double * n)()
    rr = (c_int32 * (nblocks + 1))()
    ok = lib.klu_extract(
        nptr, sptr, lp, li, lx, up, ui, ux, fp, fi, fx, pp, qq, rs, rr, byref(sym.symbolic.common)
    )
    assert ok == 1, "klu_extract failed"

    def csc(p, i, x):
        return csc_matrix(
            (np.ctypeslib.as_array(x), np.ctypeslib.as_array(i), np.ctypeslib.as_array(p)),
            shape=(n, n),
        )

    # Complete factorisation: L + U of the diagonal blocks, plus the
    # off-diagonal blocks F (kept as-is) — the fair counterpart to SuperLU's L+U.
    # nnz of the superimposed pattern (shared diagonal once) matches the spy.
    factors = (csc(lp, li, lx) + csc(up, ui, ux) + csc(fp, fi, fx)).tocsc()
    factors.eliminate_zeros()
    return factors, np.ctypeslib.as_array(rr).copy(), factors.nnz


def klu_reorder(a):
    """``J`` permuted by KLU's BTF (the matrix ``P J Q``) and the block bounds ``R``."""
    if not _klu.is_available():
        raise SystemExit("libklu.so not available")
    sym = KluSolver().analyze(a)
    s = ctypes.cast(sym.symbolic.ptr, ctypes.POINTER(KluSymbolic)).contents
    n, nblocks = s.n, s.nblocks
    p = np.ctypeslib.as_array(s.P, (n,)).copy()
    q = np.ctypeslib.as_array(s.Q, (n,)).copy()
    r = np.ctypeslib.as_array(s.R, (nblocks + 1,)).copy()
    return a[p][:, q].tocsc(), r


def blocks(ax, r):
    for k in range(len(r) - 1):
        lo, size = r[k] - 0.5, r[k + 1] - r[k]
        ax.add_patch(
            Rectangle((lo, lo), size, size, facecolor=DARKGREEN, alpha=0.16, edgecolor="none")
        )


def spy(ax, m, title, title_color=DARKBLUE):
    ax.spy(m, markersize=3.2, marker="s", color=DARKBLUE)
    ax.set_title(title, fontsize=9, color=title_color)
    n = m.shape[0]
    ax.set_xlim(-0.5, n - 0.5)
    ax.set_ylim(n - 0.5, -0.5)
    ax.tick_params(length=0, labelsize=6)
    ax.set_xticks([0, n - 1])
    ax.set_yticks([0, n - 1])


def main() -> None:
    intervals = 10
    a = stacked_jacobian(horizon=50.0, intervals=intervals)
    n, nvars = a.shape[0], a.shape[0] // (intervals + 1)
    su, su_nnz = superlu_factors(a)
    knb, _, knb_nnz = klu_factors(a, btf=False)
    pjq, rpq = klu_reorder(a)
    kbt, r, kbt_nnz = klu_factors(a, btf=True)

    fig, axs = plt.subplots(1, 5, figsize=(14.6, 2.9))
    spy(axs[0], a, f"stacked Jacobian $J$\n({a.nnz} nonzeros)")
    spy(axs[1], su, f"SuperLU factors\n({su_nnz} nonzeros)")
    spy(axs[2], knb, f"KLU factors, no BTF\n({knb_nnz} nonzeros)")
    blocks(axs[3], rpq)
    spy(axs[3], pjq, f"$P J Q$ — BTF reorder\n({pjq.nnz} nonzeros)", title_color=DARKGREEN)
    blocks(axs[4], r)
    spy(axs[4], kbt, f"KLU factors, BTF\n({kbt_nnz} nonzeros)", title_color=DARKGREEN)

    fig.suptitle(
        f"rbc, $n={n}$ (${nvars}$ vars $\\times$ ${intervals + 1}$ grid points)",
        fontsize=8,
        color="0.35",
        y=0.03,
    )
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    out = HERE / "btf_figure.pdf"
    fig.savefig(out)
    print(f"wrote {out}  (J {a.nnz}; SuperLU {su_nnz}; KLU-noBTF {knb_nnz}; KLU+BTF {kbt_nnz})")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Adaptive refinement at the ZLB kink.

Generates ``exp_adaptive.pdf`` for the slides — two panels on the nonlinear NK
model with a binding zero lower bound (anticipated TFP boom):

- left, the solution: the policy rate ``R`` (floored at zero over the binding
  interval, shaded) and inflation ``pi``, with the adaptive grid's nodes shown
  beneath — they cluster at the endogenous ZLB-exit kink;
- right, accuracy per node: max error against a fine reference vs the node
  count, for uniform Crank–Nicolson and Gauss-4, and for adaptive refinement.
  Adaptive reaches a given accuracy with far fewer nodes — but only with the
  ``residual`` monitor, which (unlike ``richardson``) is not fooled by the
  order collapse at the kink.

    python doc/perfect-foresight/exp_adaptive.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

import continuo

plt.rcParams.update(
    {
        "font.size": 15,
        "axes.titlesize": 15,
        "axes.labelsize": 14,
        "legend.fontsize": 11,
        "xtick.labelsize": 12,
        "ytick.labelsize": 12,
        "lines.linewidth": 1.9,
    }
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
T = 25.0


def _err(sol, reference, query) -> float:
    def gap(name):
        return np.interp(query, sol.t, sol[name]) - np.interp(query, reference.t, reference[name])

    return max(float(np.max(np.abs(gap(name)))) for name in ("R", "pi"))


def main() -> None:
    model = continuo.parse(ROOT / "examples" / "nk-nonlinear" / "baseline.mod")
    reference = model.simul(horizon=T, intervals=12000)
    query = np.linspace(0.0, T, 4000)

    adaptive = model.simul(horizon=T, intervals=150, adapt=1e-5, monitor="residual")

    fig, (ax_sol, ax_acc) = plt.subplots(1, 2, figsize=(11, 4.3))

    # -- left: the solution + adaptive node placement
    binding = reference.t[np.asarray(reference["R"]) < 1e-7]
    if binding.size:
        ax_sol.axvspan(binding.min(), binding.max(), color="0.9", label="ZLB binds")
    ax_sol.plot(reference.t, reference["R"], color="C0", lw=1.6, label="R (policy rate)")
    ax_sol.plot(reference.t, reference["pi"], color="C3", lw=1.6, label="pi (inflation)")
    ax_sol.axhline(0.0, color="0.5", lw=0.6)
    ax_sol.plot(adaptive.t, np.full_like(adaptive.t, -0.085), "|", color="0.2", ms=6, mew=0.6)
    ax_sol.text(T, -0.085, "  adaptive nodes", color="0.2", fontsize=7, va="center")
    ax_sol.set_xlim(0, 8)
    ax_sol.set_title("Anticipated boom drives R to the ZLB;\nnodes cluster at the exit")
    ax_sol.set_xlabel("time")
    ax_sol.legend(loc="lower right", fontsize=10)

    # -- right: accuracy per node
    uni_ns = [150, 300, 600, 1200, 2400]
    for scheme, order, label, color in (
        ("crank_nicolson", None, "uniform CN", "0.0"),
        ("gauss", 4, "uniform gauss-4", "C0"),
    ):
        pts = [(model.simul(horizon=T, intervals=n, scheme=scheme, order=order)) for n in uni_ns]
        ax_acc.loglog(
            [len(s.t) for s in pts],
            [_err(s, reference, query) for s in pts],
            "o-",
            color=color,
            lw=1.3,
            ms=4,
            label=label,
        )
    for scheme, order, mon, label, color, marker in (
        ("crank_nicolson", None, "residual", "adaptive CN (residual)", "C2", "s"),
        ("gauss", 4, "residual", "adaptive gauss-4 (residual)", "C1", "^"),
        ("gauss", 4, "richardson", "adaptive gauss-4 (richardson)", "C3", "x"),
    ):
        pts = [
            model.simul(
                horizon=T, intervals=150, scheme=scheme, order=order, adapt=tol, monitor=mon
            )
            for tol in (1e-3, 1e-4, 1e-5, 1e-6)
        ]
        ax_acc.loglog(
            [len(s.t) for s in pts],
            [_err(s, reference, query) for s in pts],
            marker + "--",
            color=color,
            lw=1.1,
            ms=5,
            label=label,
        )
    ax_acc.set_title("Accuracy per node:\nadaptive + residual wins at the kink")
    ax_acc.set_xlabel("nodes")
    ax_acc.set_ylabel("max error (R, pi)")
    ax_acc.grid(True, which="both", ls=":", lw=0.4)
    ax_acc.legend(loc="upper right", fontsize=9)

    fig.tight_layout()
    out = HERE / "exp_adaptive.pdf"
    fig.savefig(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

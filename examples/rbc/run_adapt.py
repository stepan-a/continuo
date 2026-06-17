#!/usr/bin/env python3
"""Adaptive vs uniform grids on the RBC transition.

Run from anywhere with continuo importable (e.g. ``pip install -e .``):

    python examples/rbc/run_adapt.py

The baseline RBC response to a transitory productivity shock is *fast early*
(the saddle-path adjustment) and *slow late* (the long mean-reverting tail) —
the textbook case for a non-uniform grid. This compares the uniform grid from
the model's ``simulate`` directive with adaptive refinement
(``simul(adapt=tol)``), against a fine reference, and writes
examples/rbc/adapt.png: the capital path with the adaptive nodes, and the
adaptive step size against time (fine near t=0, coarse in the tail).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

import continuo

HERE = Path(__file__).resolve().parent
HORIZON = 50.0  # the rbc.mod simulate horizon (overriding N needs the horizon too)
TOL = 1e-6


def _max_error(sol, reference) -> float:
    """Max |ΔK| against a fine reference, sampled at the solution's own times."""
    ref_k = np.interp(sol.t, reference.t, reference["K"])
    return float(np.max(np.abs(sol["K"] - ref_k)))


def main() -> None:
    model = continuo.parse(HERE / "rbc.mod")
    reference = model.simul(horizon=HORIZON, intervals=4000)  # fine uniform reference

    uniform = model.simul()
    adaptive = model.simul(adapt=TOL, monitor="richardson")

    for label, sol in (("uniform", uniform), ("adaptive", adaptive)):
        print(
            f"{label:9s} nodes={len(sol.t):5d}  max|ΔK|={_max_error(sol, reference):.2e}  "
            f"equidistribution_ratio={sol.diagnostics['equidistribution_ratio']:.1f}"
        )
    # A uniform grid with the adaptive node count, to compare like for like.
    matched = model.simul(horizon=HORIZON, intervals=len(adaptive.t) - 1)
    print(
        f"uniform@{len(matched.t)} nodes  max|ΔK|={_max_error(matched, reference):.2e} "
        f"(vs adaptive {_max_error(adaptive, reference):.2e} at the same budget)"
    )

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("\nmatplotlib not installed — skipping the plot.")
        return

    fig, (ax_k, ax_h) = plt.subplots(2, 1, figsize=(9, 7))
    ax_k.plot(uniform.t, uniform["K"], color="0.7", lw=2, label="uniform")
    ax_k.plot(adaptive.t, adaptive["K"], "o-", ms=3, lw=1, color="C0", label="adaptive nodes")
    ax_k.set_title("Capital transition: adaptive nodes cluster on the fast early adjustment")
    ax_k.set_xlabel("time")
    ax_k.set_ylabel("K")
    ax_k.legend(loc="best")

    mid = 0.5 * (adaptive.t[:-1] + adaptive.t[1:])
    ax_h.semilogy(mid, np.diff(adaptive.t), color="C0")
    ax_h.set_title("Adaptive step size: fine near the transient, coarse in the tail")
    ax_h.set_xlabel("time")
    ax_h.set_ylabel("step size dt")
    ax_h.grid(True, which="both", ls=":", lw=0.5)

    fig.tight_layout()
    out = HERE / "adapt.png"
    fig.savefig(out, dpi=120)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()

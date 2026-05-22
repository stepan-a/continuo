#!/usr/bin/env python3
"""Solve every NK / ZLB scenario in this directory and plot them on common axes.

Run from anywhere, with continuo importable (e.g. ``pip install -e .``):

    python examples/nk/run_nk.py

For each scenario it parses the model, simulates the perfect-foresight path and
prints a one-line summary. If matplotlib is installed it also overlays the four
variables (output gap x, inflation pi, policy rate i, and natural rate rnat)
across scenarios into examples/nk/nk.png.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

import continuo

HERE = Path(__file__).resolve().parent

# label -> (model file, RLOW, DUR). Order controls the plot legend.
# RLOW/DUR mirror the rnat path in each .mod, used to recover rnat in Python.
SCENARIOS = {
    "mild (RLOW=0.01, DUR=2)": ("nk_mild.mod", 0.01, 2.0),
    "trap (RLOW=-0.04, DUR=2)": ("nk_trap.mod", -0.04, 2.0),
    "deep trap (RLOW=-0.04, DUR=4)": ("nk_deep_trap.mod", -0.04, 4.0),
}

RHO = 0.02  # baseline natural rate (= rho in common.mod)


def main() -> None:
    solutions = {}
    for label, (filename, _rlow, _dur) in SCENARIOS.items():
        sol = continuo.parse(HERE / filename).simul()
        solutions[label] = sol
        print(
            f"{label:32s} "
            f"x_min = {sol['x'].min():.4f}   "
            f"pi_min = {sol['pi'].min():.4f}   "
            f"i_min = {sol['i'].min():.4f}"
        )

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("\nmatplotlib not installed — skipping the plot.")
        return

    fig, axes = plt.subplots(2, 2, figsize=(11, 7), sharex=True)
    panels = (
        ("x", "Output gap x"),
        ("pi", "Inflation pi"),
        ("i", "Policy rate i (ZLB floor at 0)"),
        ("rnat", "Natural rate rnat"),
    )
    for ax, (name, title) in zip(axes.flat, panels, strict=True):
        for label, sol in solutions.items():
            if name == "rnat":
                # rnat is exogenous: recover its path from RLOW/DUR.
                _, rlow, dur = SCENARIOS[label]
                t = np.asarray(sol.t)
                series = RHO + (rlow - RHO) * ((t >= 0) & (t < dur))
            else:
                series = sol[name]
            ax.plot(sol.t, series, lw=1.6, label=label)
        ax.set_title(title)
        ax.axhline(0.0, color="0.7", lw=0.8, zorder=0)
    for ax in axes[-1]:
        ax.set_xlabel("time")
    axes[0, 0].legend(loc="best", fontsize=8)
    fig.suptitle("NK liquidity trap: demand-shock scenarios")
    fig.tight_layout()

    out = HERE / "nk.png"
    fig.savefig(out, dpi=120)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()

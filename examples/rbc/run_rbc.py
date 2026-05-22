#!/usr/bin/env python3
"""Solve every RBC scenario in this directory and plot them on common axes.

Run from anywhere, with continuo importable (e.g. ``pip install -e .``):

    python examples/rbc/run_rbc.py

For each scenario it parses the model, simulates the perfect-foresight path and
prints a one-line summary. If matplotlib is installed it also overlays the four
variables (A, K, C, Y) across scenarios into examples/rbc/rbc.png.
"""

from __future__ import annotations

from pathlib import Path

import continuo

HERE = Path(__file__).resolve().parent

# label -> model file. Order controls the plot legend.
SCENARIOS = {
    "baseline (initial impulse)": "rbc.mod",
    "sustained (permanent, t=0)": "rbc_sustained.mod",
    "transitory (boom 5–15)": "rbc_transitory.mod",
    "anticipated (step at t=10)": "rbc_anticipated.mod",
    "surprise (step at t=10)": "rbc_surprise.mod",
}


def main() -> None:
    solutions = {}
    for label, filename in SCENARIOS.items():
        sol = continuo.parse(HERE / filename).simul()
        solutions[label] = sol
        print(
            f"{label:28s} "
            f"A: {sol['A'][0]:.3f} -> {sol['A'][-1]:.3f}   "
            f"C(0) = {sol['C'][0]:.4f}   "
            f"K: {sol['K'][0]:.3f} -> {sol['K'][-1]:.3f}"
        )

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("\nmatplotlib not installed — skipping the plot.")
        return

    fig, axes = plt.subplots(2, 2, figsize=(11, 7), sharex=True)
    for ax, name, title in zip(
        axes.flat,
        ("A", "K", "C", "Y"),
        ("Productivity A", "Capital K", "Consumption C", "Output Y"),
        strict=True,
    ):
        for label, sol in solutions.items():
            ax.plot(sol.t, sol[name], lw=1.6, label=label)
        ax.set_title(title)
    for ax in axes[-1]:
        ax.set_xlabel("time")
    axes[0, 0].legend(loc="best", fontsize=8)
    fig.suptitle("RBC: productivity-shock scenarios")
    fig.tight_layout()

    out = HERE / "rbc.png"
    fig.savefig(out, dpi=120)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()

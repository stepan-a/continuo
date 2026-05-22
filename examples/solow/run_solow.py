#!/usr/bin/env python3
"""Solve every Solow–Swan scenario in this directory and plot them on common axes.

Run from anywhere, with continuo importable (e.g. ``pip install -e .``):

    python examples/solow/run_solow.py

For each scenario it parses the model, simulates the transition path and prints
a one-line summary. If matplotlib is installed it also overlays capital K and
output Y across scenarios into examples/solow/solow.png.
"""

from __future__ import annotations

from pathlib import Path

import continuo

HERE = Path(__file__).resolve().parent

# label -> model file. Order controls the plot legend.
SCENARIOS = {
    "convergence (K0 = 30% of K*)": "solow.mod",
    "savings rise (0.2 -> 0.3)": "solow_savings.mod",
    "productivity rise (A 1 -> 1.3)": "solow_productivity.mod",
}


def main() -> None:
    solutions = {}
    for label, filename in SCENARIOS.items():
        sol = continuo.parse(HERE / filename).simul()
        solutions[label] = sol
        print(
            f"{label:32s} "
            f"K: {sol['K'][0]:.3f} -> {sol['K'][-1]:.3f}   "
            f"Y: {sol['Y'][0]:.3f} -> {sol['Y'][-1]:.3f}"
        )

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("\nmatplotlib not installed — skipping the plot.")
        return

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharex=True)
    for ax, name, title in zip(
        axes.flat,
        ("K", "Y"),
        ("Capital K", "Output Y"),
        strict=True,
    ):
        for label, sol in solutions.items():
            line = ax.plot(sol.t, sol[name], lw=1.6, label=label)[0]
            # dashed reference at each scenario's terminal (steady-state) level
            ax.axhline(sol[name][-1], color=line.get_color(), lw=0.7, ls=":")
        ax.set_title(title)
        ax.set_xlabel("time")
    axes[0].legend(loc="best", fontsize=8)
    fig.suptitle("Solow–Swan: convergence and comparative dynamics")
    fig.tight_layout()

    out = HERE / "solow.png"
    fig.savefig(out, dpi=120)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()

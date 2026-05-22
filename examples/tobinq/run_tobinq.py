#!/usr/bin/env python3
"""Solve every Tobin's q scenario in this directory and plot them on common axes.

Run from anywhere, with continuo importable (e.g. ``pip install -e .``):

    python examples/tobinq/run_tobinq.py

For each scenario it parses the model, simulates the perfect-foresight path and
prints a one-line summary. If matplotlib is installed it also overlays the four
variables (q, K, I, A) across scenarios into examples/tobinq/tobinq.png.
"""

from __future__ import annotations

from pathlib import Path

import continuo

HERE = Path(__file__).resolve().parent

# label -> model file. Order controls the plot legend.
SCENARIOS = {
    "unanticipated permanent (t=0)": "tobinq.mod",
    "anticipated (step at t=5)": "tobinq_anticipated.mod",
    "surprise (step at t=5)": "tobinq_surprise.mod",
}

# Each scenario's profitability path A(t), recovered in Python for the plot.
A_PATHS = {
    "tobinq.mod": lambda t: 1.5 + 0.0 * t,
    "tobinq_anticipated.mod": lambda t: 1.0 + 0.5 * (t >= 5),
    "tobinq_surprise.mod": lambda t: 1.0 + 0.5 * (t >= 5),
}


def main() -> None:
    solutions = {}
    a_series = {}
    for label, filename in SCENARIOS.items():
        sol = continuo.parse(HERE / filename).simul()
        solutions[label] = sol
        a_series[label] = A_PATHS[filename](sol.t)
        print(
            f"{label:32s} "
            f"q(0) = {sol['q'][0]:.4f}   "
            f"K: {sol['K'][0]:.3f} -> {sol['K'][-1]:.3f}   "
            f"I: {sol['I'][0]:.3f} -> {sol['I'][-1]:.3f}"
        )

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("\nmatplotlib not installed — skipping the plot.")
        return

    fig, axes = plt.subplots(2, 2, figsize=(11, 7), sharex=True)
    panels = (
        ("q", "Tobin's q"),
        ("K", "Capital K"),
        ("I", "Investment I"),
        ("A", "Profitability A"),
    )
    for ax, (name, title) in zip(axes.flat, panels, strict=True):
        for label, sol in solutions.items():
            series = a_series[label] if name == "A" else sol[name]
            ax.plot(sol.t, series, lw=1.6, label=label)
        ax.set_title(title)
    for ax in axes[-1]:
        ax.set_xlabel("time")
    axes[0, 0].legend(loc="best", fontsize=8)
    fig.suptitle("Tobin's q: profitability-shock scenarios")
    fig.tight_layout()

    out = HERE / "tobinq.png"
    fig.savefig(out, dpi=120)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()

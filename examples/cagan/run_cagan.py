#!/usr/bin/env python3
"""Solve every Cagan scenario in this directory and plot them on common axes.

Run from anywhere, with continuo importable (e.g. ``pip install -e .``):

    python examples/cagan/run_cagan.py

For each scenario it parses the model, simulates the perfect-foresight path and
prints a one-line summary. If matplotlib is installed it also plots the price
level `p` against the money supply `m` for each scenario into
examples/cagan/cagan.png, so the lead/lag between prices and money is visible.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

import continuo

HERE = Path(__file__).resolve().parent

# label -> (model file, money path m(t) as a function of the time grid).
# The exogenous money path is recomputed analytically to match each scenario's
# shocks block, so it can be overlaid on the simulated price level.
SCENARIOS = {
    "anticipated (step at t=5)": (
        "cagan.mod",
        lambda t: 0.2 * (t >= 5),
    ),
    "surprise (step at t=5)": (
        "cagan_surprise.mod",
        lambda t: 0.2 * (t >= 5),
    ),
    "gradual (ramp 3->9)": (
        "cagan_gradual.mod",
        lambda t: 0.2 * np.clip((t - 3) / (9 - 3), 0.0, 1.0),
    ),
}


def main() -> None:
    solutions = {}
    for label, (filename, _money) in SCENARIOS.items():
        sol = continuo.parse(HERE / filename).simul()
        solutions[label] = sol
        t = np.asarray(sol.t)
        p5 = float(np.interp(5.0, t, sol["p"]))
        print(
            f"{label:28s} "
            f"p(0) = {sol['p'][0]:.4f}   "
            f"p(t=5) = {p5:.4f}   "
            f"p(end) = {sol['p'][-1]:.4f}"
        )

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("\nmatplotlib not installed — skipping the plot.")
        return

    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2), sharex=True, sharey=True)
    for ax, (label, (_filename, money)) in zip(axes, SCENARIOS.items(), strict=True):
        sol = solutions[label]
        t = np.asarray(sol.t)
        ax.plot(t, money(t), lw=1.6, ls="--", color="tab:gray", label="money $m$")
        ax.plot(t, sol["p"], lw=2.0, color="tab:blue", label="price $p$")
        ax.set_title(label)
        ax.set_xlabel("time")
        ax.legend(loc="best", fontsize=8)
    axes[0].set_ylabel("log level")
    fig.suptitle("Cagan model: price level $p$ leads the money supply $m$")
    fig.tight_layout()

    out = HERE / "cagan.png"
    fig.savefig(out, dpi=120)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Solve the Goodwin growth-cycle scenarios and plot them.

Run from anywhere with continuo importable (e.g. ``pip install -e .``):

    python examples/goodwin/run_goodwin.py

For each scenario it parses the model, simulates the (autonomous) path, and
prints a one-line summary. With matplotlib installed it writes
examples/goodwin/goodwin.png: time series of the employment rate and wage
share, plus the phase portrait showing the nested closed orbits.
"""

from __future__ import annotations

from pathlib import Path

import continuo

HERE = Path(__file__).resolve().parent

# label -> model file, in order of increasing amplitude.
SCENARIOS = {
    "small": "goodwin_small.mod",
    "moderate": "goodwin.mod",
    "large": "goodwin_large.mod",
}


def main() -> None:
    solutions = {}
    fixed_point = None
    for label, filename in SCENARIOS.items():
        model = continuo.parse(HERE / filename)
        sol = model.simul()
        solutions[label] = sol
        fixed_point = model.steady_state()  # same for every scenario
        print(
            f"{label:9s} v in [{sol['v'].min():.3f}, {sol['v'].max():.3f}]   "
            f"u in [{sol['u'].min():.3f}, {sol['u'].max():.3f}]"
        )
    print(f"\nfixed point (centre of the orbits): v* = {fixed_point['v']:.3f}, "
          f"u* = {fixed_point['u']:.3f}")

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("\nmatplotlib not installed — skipping the plot.")
        return

    fig = plt.figure(figsize=(11, 7))
    ax_v = fig.add_subplot(2, 2, 1)
    ax_u = fig.add_subplot(2, 2, 2)
    ax_phase = fig.add_subplot(2, 1, 2)

    for label, sol in solutions.items():
        ax_v.plot(sol.t, sol["v"], lw=1.4, label=label)
        ax_u.plot(sol.t, sol["u"], lw=1.4, label=label)
        ax_phase.plot(sol["v"], sol["u"], lw=1.2, label=f"{label} amplitude")

    ax_v.axhline(fixed_point["v"], color="0.6", ls="--", lw=1)
    ax_v.set_title("Employment rate v")
    ax_v.set_xlabel("time")
    ax_v.legend(loc="best", fontsize=8)

    ax_u.axhline(fixed_point["u"], color="0.6", ls="--", lw=1)
    ax_u.set_title("Wage share u")
    ax_u.set_xlabel("time")

    ax_phase.plot(fixed_point["v"], fixed_point["u"], "k+", ms=12, mew=2,
                  label="fixed point")
    ax_phase.set_title("Phase portrait (nested closed orbits)")
    ax_phase.set_xlabel("employment rate v")
    ax_phase.set_ylabel("wage share u")
    ax_phase.legend(loc="best", fontsize=8)

    fig.suptitle("Goodwin growth cycle")
    fig.tight_layout()

    out = HERE / "goodwin.png"
    fig.savefig(out, dpi=120)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()

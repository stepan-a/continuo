#!/usr/bin/env python3
"""Solve the three nonlinear-NK variants and overlay them on common axes.

For each scenario it parses the model, simulates the perfect-foresight
liquidity-trap path, prints a one-line summary, and (if matplotlib is
available) writes examples/nk-nonlinear/nk-nonlinear.png with the four
canonical panels: the consumption gap from steady state, inflation,
policy rate (with the zero lower bound visible), and the exogenous
natural rate that drives all three.

Run from anywhere with continuo importable (e.g. ``pip install -e .``):

    python examples/nk-nonlinear/run_nk_nonlinear.py
"""

from __future__ import annotations

from pathlib import Path

import continuo
import numpy as np

HERE = Path(__file__).resolve().parent

# label -> model file. Order controls the legend.
SCENARIOS = {
    "baseline (no habit)": "baseline.mod",
    "external habit (h=0.7)": "external_habit.mod",
    "internal habit (h=0.7)": "internal_habit.mod",
}


def main() -> None:
    runs = []
    for label, filename in SCENARIOS.items():
        model = continuo.parse(HERE / filename)
        ss = model.steady_state(exogenous={"rnat": 0.02})
        sol = model.simul()
        c_gap = (sol["C"] / ss["C"] - 1.0) * 100.0
        zlb_frac = float(np.mean(sol["R"] < 1e-4))
        runs.append((label, sol, ss, c_gap))
        print(
            f"{label:24s} "
            f"C*={ss['C']:.4f}  "
            f"C-gap min={c_gap.min():+6.2f}%  "
            f"pi min={sol['pi'].min():+.4f}  "
            f"R min={sol['R'].min():.4f}  "
            f"ZLB time={zlb_frac * 100:4.1f}%"
        )

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("\nmatplotlib not installed — skipping the plot.")
        return

    fig, axes = plt.subplots(2, 2, figsize=(11, 7), sharex=True)
    panels = [
        ("C-gap (% from steady state)", lambda sol, ss: (sol["C"] / ss["C"] - 1) * 100),
        ("Inflation pi", lambda sol, ss: sol["pi"]),
        ("Policy rate R", lambda sol, ss: sol["R"]),
        ("Natural rate rnat", None),  # recovered analytically below
    ]
    for ax, (title, getter) in zip(axes.flat, panels, strict=True):
        for label, sol, ss, _ in runs:
            if getter is not None:
                ax.plot(sol.t, getter(sol, ss), lw=1.6, label=label)
        ax.set_title(title)

    # rnat is the same exogenous path across scenarios; reconstruct it on
    # the grid analytically: rho - 0.06 * pulse(t, 0, 2).
    t = runs[0][1].t
    rnat = 0.02 - 0.06 * ((t >= 0) & (t < 2)).astype(float)
    axes[1, 1].plot(t, rnat, lw=1.6, color="0.4")

    # mark the ZLB floor at 0 on the policy-rate panel
    axes[1, 0].axhline(0, color="0.6", ls="--", lw=1)

    for ax in axes[-1]:
        ax.set_xlabel("time")
    axes[0, 0].legend(loc="best", fontsize=8)
    fig.suptitle("Nonlinear NK liquidity trap: baseline vs external vs internal habit")
    fig.tight_layout()

    out = HERE / "nk-nonlinear.png"
    fig.savefig(out, dpi=120)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()

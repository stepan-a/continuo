#!/usr/bin/env python3
"""Solve every Dornbusch scenario in this directory and plot them on common axes.

Run from anywhere, with continuo importable (e.g. ``pip install -e .``):

    python examples/dornbusch/run_dornbusch.py

For each scenario it parses the model, simulates the perfect-foresight path and
prints a one-line summary (impact and long-run exchange rate, plus the impact
overshoot for the unanticipated case). If matplotlib is installed it also
overlays the exchange rate s, the price level p, the interest rate i and the
money supply m across scenarios into examples/dornbusch/dornbusch.png.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

import continuo

HERE = Path(__file__).resolve().parent

# label -> (model file, money path as a function of time). Order controls the
# plot legend. The money path mirrors each scenario's `shocks` block so we can
# recover m(t) in Python for the bottom-right panel.
SCENARIOS = {
    "unanticipated (permanent, t=0)": (
        "dornbusch.mod",
        lambda t: np.full_like(t, 0.1),
    ),
    "anticipated (step at t=5)": (
        "dornbusch_anticipated.mod",
        lambda t: np.where(t >= 5, 0.1, 0.0),
    ),
    "gradual (ramp over [0,10])": (
        "dornbusch_gradual.mod",
        lambda t: 0.1 * np.clip(t / 10.0, 0.0, 1.0),
    ),
}


def main() -> None:
    solutions = {}
    money = {}
    sstar = {}
    for label, (filename, mpath) in SCENARIOS.items():
        model = continuo.parse(HERE / filename)
        sol = model.simul()
        solutions[label] = sol
        money[label] = mpath(np.asarray(sol.t, dtype=float))
        # long-run exchange rate: steady state at the terminal money level
        m_end = float(money[label][-1])
        sstar[label] = model.steady_state(exogenous={"m": m_end})["s"]
        overshoot = sol["s"][0] - sol["s"][-1]
        print(
            f"{label:32s} "
            f"s(0) = {sol['s'][0]:+.4f}   "
            f"s(end) = {sol['s'][-1]:+.4f}   "
            f"overshoot s(0)-s(end) = {overshoot:+.4f}"
        )

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("\nmatplotlib not installed — skipping the plot.")
        return

    fig, axes = plt.subplots(2, 2, figsize=(11, 7), sharex=True)
    panels = (
        ("s", "Exchange rate s"),
        ("p", "Price level p"),
        ("i", "Interest rate i"),
        (None, "Money supply m"),
    )
    for ax, (name, title) in zip(axes.flat, panels, strict=True):
        for label, sol in solutions.items():
            if name is None:
                ax.plot(sol.t, money[label], lw=1.6, label=label)
            else:
                line, = ax.plot(sol.t, sol[name], lw=1.6, label=label)
                if name == "s":
                    # mark each scenario's long-run exchange rate
                    ax.axhline(
                        sstar[label],
                        color=line.get_color(),
                        lw=0.8,
                        ls=":",
                        alpha=0.7,
                    )
        ax.set_title(title)
    for ax in axes[-1]:
        ax.set_xlabel("time")
    axes[0, 0].legend(loc="best", fontsize=8)
    fig.suptitle("Dornbusch: exchange-rate overshooting under monetary expansion")
    fig.tight_layout()

    out = HERE / "dornbusch.png"
    fig.savefig(out, dpi=120)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()

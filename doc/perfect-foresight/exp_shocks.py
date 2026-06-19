#!/usr/bin/env python3
"""Anticipated vs surprise shocks at the ZLB.

Generates ``exp_shocks.pdf`` for the slides — the nonlinear NK model under two
belief structures for the same kind of productivity boom:

- *anticipated*: the whole boom is known at t=0 (one belief, one segment);
- *surprise*: agents expect no boom until, at t=1.5, they learn of a (larger)
  boom — a second belief, so the horizon splits into two segments glued at the
  reveal. The reveal time is placed on an exact grid node (shock-aligned),
  while the ZLB-exit kink inside each segment is endogenous.

    python doc/perfect-foresight/exp_shocks.py
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
REVEAL = 1.5

BASE = (ROOT / "examples" / "nk-nonlinear" / "baseline.mod").read_text()
SURPRISE = BASE.replace(
    "  path = 1 + 0.12 * pulse(t, 0, 3);",
    f"  path at t=0 = 1;\n  path at t={REVEAL} = 1 + 0.20 * pulse(t, {REVEAL}, {REVEAL + 3});",
)


def _pulse(t, a, b):
    return ((t >= a) & (t < b)).astype(float)


def main() -> None:
    anticipated = continuo.parse(ROOT / "examples" / "nk-nonlinear" / "baseline.mod").simul()
    surprise = continuo.parse_string(SURPRISE).simul()

    t = np.linspace(0.0, T, 2000)
    a_ant = 1 + 0.12 * _pulse(t, 0, 3)
    a_sur = np.where(t < REVEAL, 1.0, 1 + 0.20 * _pulse(t, REVEAL, REVEAL + 3))

    fig, (ax_a, ax_r, ax_pi) = plt.subplots(1, 3, figsize=(14, 4.2))

    scenarios = ((anticipated, "C0", "anticipated"), (surprise, "C3", "surprise"))

    # -- left: the realised shock (one belief vs a surprise reveal)
    ax_a.plot(t, a_ant, color="C0", lw=1.6, label="anticipated")
    ax_a.plot(t, a_sur, color="C3", lw=1.6, label="surprise (reveal t=1.5)")
    ax_a.axvline(REVEAL, color="0.6", ls="--", lw=0.8)
    ax_a.set_xlim(0, 8)
    ax_a.set_title("Realised productivity A:\none belief vs a surprise reveal")
    ax_a.set_xlabel("time")
    ax_a.set_ylabel("A")
    ax_a.legend(loc="upper right", fontsize=9)

    # -- middle: the policy rate at the zero lower bound
    for sol, color, label in scenarios:
        ax_r.plot(sol.t, sol["R"], color=color, lw=1.6, label=label)
        binding = np.asarray(sol.t)[np.asarray(sol["R"]) < 1e-7]
        if binding.size:
            ax_r.axvspan(binding.min(), binding.max(), color=color, alpha=0.10)
    ax_r.axhline(0.0, color="0.4", lw=1.1)
    ax_r.text(0.1, 0.0, "ZLB", color="0.4", fontsize=9, va="bottom")
    ax_r.axvline(REVEAL, color="0.6", ls="--", lw=0.8)
    ax_r.set_xlim(0, 8)
    ax_r.set_title("Policy rate R at the ZLB:\nsurprise binds later, exits later")
    ax_r.set_xlabel("time")
    ax_r.set_ylabel("R")
    ax_r.legend(loc="lower right", fontsize=9)

    # -- right: the inflation response
    for sol, color, label in scenarios:
        ax_pi.plot(sol.t, sol["pi"], color=color, lw=1.6, label=label)
    ax_pi.axhline(0.0, color="0.5", lw=0.6)
    ax_pi.axvline(REVEAL, color="0.6", ls="--", lw=0.8, label="reveal node")
    ax_pi.set_xlim(0, 8)
    ax_pi.set_title("Inflation:\nsurprise deepens the deflation")
    ax_pi.set_xlabel("time")
    ax_pi.set_ylabel("pi")
    ax_pi.legend(loc="lower right", fontsize=9)

    fig.tight_layout()
    out = HERE / "exp_shocks.pdf"
    fig.savefig(out)
    print(
        f"wrote {out}  (anticipated segments={len(anticipated.segments)}, "
        f"surprise segments={len(surprise.segments)})"
    )


if __name__ == "__main__":
    main()

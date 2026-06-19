#!/usr/bin/env python3
"""Convergence of the discretisation schemes: smooth vs a ZLB kink.

Generates ``exp_convergence.pdf`` for the slides — two log–log panels of the
max error against the number of intervals ``N``:

- left, a smooth scalar ODE (K' = lam K): every scheme attains its nominal
  global order (the reference slopes);
- right, the nonlinear NK model with a binding zero lower bound: the solution
  is only C0/C1 at the (endogenous) ZLB exit, so *every* scheme degrades to
  order ~1 and the high-order families lose their advantage.

Run before building the deck (the CI slides job does this):

    python doc/perfect-foresight/exp_convergence.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

import continuo

# Larger fonts so the figure stays legible when scaled onto a slide.
plt.rcParams.update(
    {
        "font.size": 15,
        "axes.titlesize": 15,
        "axes.labelsize": 14,
        "legend.fontsize": 12,
        "xtick.labelsize": 12,
        "ytick.labelsize": 12,
        "lines.linewidth": 1.9,
    }
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

# Full scheme sweep, coloured by family, dashed by rising order.
SCHEMES = [
    ("crank_nicolson", None, "crank_nicolson", "0.0", "-"),
    ("gauss", 2, "gauss 2", "C0", ":"),
    ("gauss", 4, "gauss 4", "C0", "--"),
    ("gauss", 6, "gauss 6", "C0", "-"),
    ("radau", 1, "radau 1", "C3", ":"),
    ("radau", 3, "radau 3", "C3", "--"),
    ("radau", 5, "radau 5", "C3", "-"),
    ("lobatto_iiia", 2, "lobatto 2", "C2", ":"),
    ("lobatto_iiia", 4, "lobatto 4", "C2", "--"),
    ("lobatto_iiia", 6, "lobatto 6", "C2", "-"),
]
SMOOTH_NS = [10, 20, 40, 80, 160]
ZLB_NS = [150, 300, 600, 1200, 2400]
LAM, SMOOTH_T = -0.7, 4.0

SMOOTH = f"""
var(state) K;
parameters lam;
lam = {LAM};
model;
  diff(K) = lam * K;
end;
initval;
  K = 1.0;
end;
"""


def _smooth_error(model, scheme, order, n):
    sol = model.simul(horizon=SMOOTH_T, intervals=n, scheme=scheme, order=order)
    return float(np.max(np.abs(sol["K"] - np.exp(LAM * sol.t))))


def _zlb_error(model, reference, query, ref_vals, scheme, order, n):
    sol = model.simul(horizon=25.0, intervals=n, scheme=scheme, order=order)
    return max(
        float(np.max(np.abs(np.interp(query, sol.t, sol[name]) - ref_vals[name])))
        for name in ("R", "pi")
    )


def main() -> None:
    smooth = continuo.parse_string(SMOOTH)
    zlb = continuo.parse(ROOT / "examples" / "nk-nonlinear" / "baseline.mod")
    reference = zlb.simul(horizon=25.0, intervals=12000)
    query = np.linspace(0.0, 25.0, 4000)
    ref_vals = {name: np.interp(query, reference.t, reference[name]) for name in ("R", "pi")}

    fig, (ax_s, ax_z) = plt.subplots(1, 2, figsize=(11, 4.3))

    for scheme, order, label, color, ls in SCHEMES:
        s_err = [_smooth_error(smooth, scheme, order, n) for n in SMOOTH_NS]
        ax_s.loglog(SMOOTH_NS, s_err, ls, color=color, lw=1.4, label=label)
        z_err = [_zlb_error(zlb, reference, query, ref_vals, scheme, order, n) for n in ZLB_NS]
        ax_z.loglog(ZLB_NS, z_err, ls, color=color, lw=1.4)

    # reference order slopes on the smooth panel
    base = SMOOTH_NS[0]
    for p, txt in ((2, "order 2"), (4, "order 4"), (6, "order 6")):
        ref = 5e-3 * (base / np.array(SMOOTH_NS, float)) ** p
        ax_s.loglog(SMOOTH_NS, ref, color="0.7", lw=0.8, zorder=0)
        ax_s.text(SMOOTH_NS[-1], ref[-1], f" {txt}", color="0.5", fontsize=7, va="center")
    # a single order-1 guide on the kink panel
    ref1 = 4e-1 * (ZLB_NS[0] / np.array(ZLB_NS, float))
    ax_z.loglog(ZLB_NS, ref1, color="0.7", lw=0.8, zorder=0)
    ax_z.text(ZLB_NS[-1], ref1[-1], " order 1", color="0.5", fontsize=7, va="center")

    ax_s.set_title("Smooth solution:\neach scheme attains its order")
    ax_z.set_title("Binding ZLB (a kink):\nevery scheme degrades to order ~1")
    for ax in (ax_s, ax_z):
        ax.set_xlabel("intervals N")
        ax.grid(True, which="both", ls=":", lw=0.4)
    ax_s.set_ylabel("max error")
    # Legend by family (colour); line style encodes the rising order.
    families = [
        ("Crank--Nicolson", "0.0"),
        ("Gauss", "C0"),
        ("Radau IIA", "C3"),
        ("Lobatto IIIA", "C2"),
    ]
    handles = [Line2D([0], [0], color=c, lw=2.0) for _, c in families]
    ax_s.legend(
        handles,
        [name for name, _ in families],
        loc="lower left",
        title="style: rising order (·· / -- / —)",
        title_fontsize=9,
    )

    fig.tight_layout()
    out = HERE / "exp_convergence.pdf"
    fig.savefig(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

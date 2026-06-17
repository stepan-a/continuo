#!/usr/bin/env python3
"""Higher-order discretisation on the Goodwin orbit: a convergence study.

Run from anywhere with continuo importable (e.g. ``pip install -e .``):

    python examples/goodwin/run_schemes.py

The Goodwin growth cycle is a smooth, conservative closed orbit — an ideal
test of discretisation accuracy. For a range of grid resolutions ``N`` it
solves the moderate-amplitude scenario with Crank–Nicolson (order 2),
Gauss–Legendre order 4 and Radau IIA order 5, and measures each against a
high-accuracy reference (Gauss order 6 on a very fine grid). The error falls
like ``h^p`` with the scheme's order ``p``, so the higher-order schemes reach
an accuracy at coarse ``N`` that Crank–Nicolson only approaches at very fine
``N``. With matplotlib installed it writes examples/goodwin/schemes.png: a
log–log plot of the error against ``N``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

import continuo

HERE = Path(__file__).resolve().parent

T = 120.0
RESOLUTIONS = (150, 300, 600, 1200)
# label -> (scheme, order); None order takes the family default.
SCHEMES = {
    "crank_nicolson (2)": ("crank_nicolson", None),
    "gauss (4)": ("gauss", 4),
    "radau (5)": ("radau", 5),
}


def _max_error(sol, reference) -> float:
    """Max |Δ| in v and u against the reference, sampled at ``sol``'s grid."""
    stride = (reference.t.size - 1) // (sol.t.size - 1)
    dv = np.abs(sol["v"] - reference["v"][::stride])
    du = np.abs(sol["u"] - reference["u"][::stride])
    return float(max(dv.max(), du.max()))


def main() -> None:
    model = continuo.parse(HERE / "goodwin.mod")
    reference = model.simul(scheme="gauss", order=6, horizon=T, intervals=4800)

    errors: dict[str, list[float]] = {label: [] for label in SCHEMES}
    print(f"{'N':>6}  " + "  ".join(f"{label:>20}" for label in SCHEMES))
    for n in RESOLUTIONS:
        row = []
        for label, (scheme, order) in SCHEMES.items():
            sol = model.simul(scheme=scheme, order=order, horizon=T, intervals=n)
            e = _max_error(sol, reference)
            errors[label].append(e)
            row.append(e)
        print(f"{n:>6}  " + "  ".join(f"{e:>20.2e}" for e in row))

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("\nmatplotlib not installed — skipping the plot.")
        return

    fig, ax = plt.subplots(figsize=(7, 5))
    for label in SCHEMES:
        ax.loglog(RESOLUTIONS, errors[label], "o-", lw=1.4, label=label)
    ax.set_title("Discretisation accuracy on the Goodwin orbit")
    ax.set_xlabel("grid intervals N")
    ax.set_ylabel("max error vs reference (v, u)")
    ax.grid(True, which="both", ls=":", lw=0.5)
    ax.legend(loc="best")
    fig.tight_layout()

    out = HERE / "schemes.png"
    fig.savefig(out, dpi=120)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()

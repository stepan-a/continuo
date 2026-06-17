"""Butcher tableaux for the collocation discretisation families.

Three families, all *collocation* methods that differ only in where the
stage nodes ``c`` sit; the coefficients ``A`` and ``b`` then follow from
the collocation order conditions

    C(s):  sum_l A[j,l] c_l^{k-1} = c_j^k / k      (k = 1..s)
    B(s):  sum_j b_j   c_j^{k-1} = 1 / k           (k = 1..s)

solved here as small Vandermonde systems in the monomial basis.

- **Gauss–Legendre** — interior nodes (Legendre roots); order ``2s``,
  A-stable, symmetric. ``s=1`` is the implicit midpoint (Crank–Nicolson).
- **Radau IIA** — last node at the right endpoint; order ``2s-1``,
  L-stable and stiffly accurate (``b`` equals the last row of ``A``).
- **Lobatto IIIA** — both endpoints are nodes; order ``2s-2``, A-stable;
  ``A`` has a zero first row (so it is singular, which the stage-derivative
  discretisation tolerates).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from continuo.solve.errors import SolveError

__all__ = [
    "ButcherTableau",
    "gauss",
    "radau_iia",
    "lobatto_iiia",
    "tableau_for",
    "default_order",
    "SCHEME_ORDERS",
]


@dataclass(frozen=True, eq=False)
class ButcherTableau:
    """An ``s``-stage Runge–Kutta tableau ``(c, A, b)`` for a collocation scheme."""

    c: np.ndarray
    A: np.ndarray
    b: np.ndarray

    @property
    def stages(self) -> int:
        return len(self.c)


# scheme name -> {order: number of stages}
SCHEME_ORDERS: dict[str, dict[int, int]] = {
    "gauss": {2: 1, 4: 2, 6: 3},
    "radau": {1: 1, 3: 2, 5: 3},
    "lobatto_iiia": {2: 2, 4: 3, 6: 4},
}

_DEFAULT_ORDER = {"gauss": 4, "radau": 5, "lobatto_iiia": 4}


def _from_nodes(c: np.ndarray) -> ButcherTableau:
    """Build the collocation ``A`` and ``b`` for distinct nodes ``c`` in ``[0, 1]``."""
    c = np.asarray(c, dtype=float)
    s = len(c)
    powers = np.arange(s)  # k - 1 for k = 1..s
    vander = c[None, :] ** powers[:, None]  # (s, s): [k-1, l] = c_l^{k-1}
    # b: sum_j b_j c_j^{k-1} = 1/k
    b = np.linalg.solve(vander, 1.0 / (powers + 1.0))
    # A[j, l]: sum_l A[j,l] c_l^{k-1} = c_j^k / k  (one Vandermonde solve per k, all j at once)
    rhs = (c[None, :] ** (powers[:, None] + 1)) / (powers[:, None] + 1.0)  # (s, s): [k-1, j]
    A = np.linalg.solve(vander, rhs).T  # (j, l)
    return ButcherTableau(c=c, A=A, b=b)


def _stages_for(scheme: str, order: int) -> int:
    orders = SCHEME_ORDERS[scheme]
    if order not in orders:
        allowed = ", ".join(str(o) for o in sorted(orders))
        raise SolveError(f"{scheme} supports order in {{{allowed}}}, got {order}")
    return orders[order]


def gauss(order: int) -> ButcherTableau:
    """Gauss–Legendre collocation of the given (even) order ``2, 4, 6``."""
    s = _stages_for("gauss", order)
    nodes, _ = np.polynomial.legendre.leggauss(s)  # on [-1, 1]
    return _from_nodes(np.sort((nodes + 1.0) / 2.0))


# Radau IIA nodes on [0, 1] (right endpoint included).
_RADAU_NODES = {
    1: [1.0],
    2: [1.0 / 3.0, 1.0],
    3: [(4.0 - np.sqrt(6.0)) / 10.0, (4.0 + np.sqrt(6.0)) / 10.0, 1.0],
}


def radau_iia(order: int) -> ButcherTableau:
    """Radau IIA collocation of the given (odd) order ``1, 3, 5``."""
    return _from_nodes(np.array(_RADAU_NODES[_stages_for("radau", order)]))


# Lobatto IIIA nodes on [0, 1] (both endpoints included).
_LOBATTO_NODES = {
    2: [0.0, 1.0],
    3: [0.0, 0.5, 1.0],
    4: [0.0, (5.0 - np.sqrt(5.0)) / 10.0, (5.0 + np.sqrt(5.0)) / 10.0, 1.0],
}


def lobatto_iiia(order: int) -> ButcherTableau:
    """Lobatto IIIA collocation of the given (even) order ``2, 4, 6``."""
    return _from_nodes(np.array(_LOBATTO_NODES[_stages_for("lobatto_iiia", order)]))


_FACTORY = {"gauss": gauss, "radau": radau_iia, "lobatto_iiia": lobatto_iiia}


def default_order(scheme: str) -> int:
    """The default order for a collocation family (used when ``order`` is omitted)."""
    if scheme not in _DEFAULT_ORDER:
        raise SolveError(f"unknown collocation scheme {scheme!r}")
    return _DEFAULT_ORDER[scheme]


def tableau_for(scheme: str, order: int | None = None) -> ButcherTableau:
    """The :class:`ButcherTableau` for a collocation family at a given order.

    ``order`` defaults to the family's :func:`default_order`. An unknown
    scheme or an order the family does not provide raises :class:`SolveError`.
    """
    if scheme not in _FACTORY:
        raise SolveError(f"unknown collocation scheme {scheme!r}")
    return _FACTORY[scheme](default_order(scheme) if order is None else order)

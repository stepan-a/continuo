"""Tests for the collocation tableaux and the per-interval residual.

These exercise the discretisation engine directly; it is not yet wired into
the perfect-foresight solver (that is a later step).
"""

from __future__ import annotations

import casadi as ca
import numpy as np
import pytest

from continuo.codegen.residual import build_residual
from continuo.ir import build
from continuo.parser import parse
from continuo.solve import SolveError
from continuo.solve.disc import (
    collocation_residual,
    crank_nicolson_residual,
    gauss,
    lobatto_iiia,
    radau_iia,
    tableau_for,
)

# (scheme, order) pairs across the full supported range.
ALL = [
    ("gauss", 2),
    ("gauss", 4),
    ("gauss", 6),
    ("radau", 1),
    ("radau", 3),
    ("radau", 5),
    ("lobatto_iiia", 2),
    ("lobatto_iiia", 4),
    ("lobatto_iiia", 6),
]


# --- tableau order conditions ---------------------------------------------


@pytest.mark.parametrize("scheme,order", ALL)
def test_row_sums_equal_nodes(scheme, order):
    # C(1): A·1 = c.
    tab = tableau_for(scheme, order)
    assert tab.A.sum(axis=1) == pytest.approx(tab.c)


@pytest.mark.parametrize("scheme,order", ALL)
def test_weights_sum_to_one(scheme, order):
    assert tableau_for(scheme, order).b.sum() == pytest.approx(1.0)


@pytest.mark.parametrize("scheme,order", ALL)
def test_quadrature_reaches_the_family_order(scheme, order):
    # B(p): sum_j b_j c_j^{k-1} = 1/k for k = 1..order.
    tab = tableau_for(scheme, order)
    for k in range(1, order + 1):
        assert (tab.b * tab.c ** (k - 1)).sum() == pytest.approx(1.0 / k)


@pytest.mark.parametrize("scheme,order", ALL)
def test_collocation_C_condition(scheme, order):
    # C(s): sum_l A[j,l] c_l^{k-1} = c_j^k / k for k = 1..s.
    tab = tableau_for(scheme, order)
    for k in range(1, tab.stages + 1):
        assert tab.A @ (tab.c ** (k - 1)) == pytest.approx(tab.c**k / k)


# --- known closed-form tableaux -------------------------------------------


def test_gauss_order2_is_implicit_midpoint():
    tab = gauss(2)
    expected_a = np.array([[0.5]])
    assert tab.c == pytest.approx([0.5])
    assert np.allclose(tab.A, expected_a)
    assert tab.b == pytest.approx([1.0])


def test_gauss_order4_nodes_and_weights():
    tab = gauss(4)
    assert tab.c == pytest.approx([0.5 - np.sqrt(3) / 6, 0.5 + np.sqrt(3) / 6])
    assert tab.b == pytest.approx([0.5, 0.5])


def test_radau_order3_matches_known_tableau():
    tab = radau_iia(3)
    expected_a = np.array([[5 / 12, -1 / 12], [3 / 4, 1 / 4]])
    assert tab.c == pytest.approx([1 / 3, 1.0])
    assert np.allclose(tab.A, expected_a)
    assert tab.b == pytest.approx([3 / 4, 1 / 4])


def test_radau_is_stiffly_accurate():
    # b equals the last row of A (so x_{i+1} is the last stage state).
    tab = radau_iia(5)
    assert tab.A[-1] == pytest.approx(tab.b)


def test_lobatto_order4_matches_simpson():
    tab = lobatto_iiia(4)
    expected_a = np.array([[0, 0, 0], [5 / 24, 1 / 3, -1 / 24], [1 / 6, 2 / 3, 1 / 6]])
    assert tab.c == pytest.approx([0.0, 0.5, 1.0])
    assert np.allclose(tab.A, expected_a)
    assert tab.b == pytest.approx([1 / 6, 2 / 3, 1 / 6])


def test_lobatto_first_row_is_zero():
    assert lobatto_iiia(4).A[0] == pytest.approx([0.0, 0.0, 0.0])


# --- invalid scheme / order -----------------------------------------------


def test_unknown_scheme_rejected():
    with pytest.raises(SolveError, match="unknown collocation scheme"):
        tableau_for("sdirk", 3)


def test_unsupported_order_rejected():
    with pytest.raises(SolveError, match="order"):
        tableau_for("gauss", 3)


def test_default_order_used_when_omitted():
    # gauss default order is 4 (two stages).
    assert tableau_for("gauss").stages == 2
    assert tableau_for("radau").stages == 3
    assert tableau_for("lobatto_iiia").stages == 3


# --- per-interval residual ------------------------------------------------

# A pure-ODE model (no algebraic variables): diff(K) = lam*K.
ODE = "var(state) K;\nparameters lam;\nlam = -0.5;\nmodel;\n  diff(K) = lam * K;\nend;"
# A model with an algebraic variable: diff(K) = lam*Y, Y = K.
DAE = (
    "var(state) K;\nvar Y;\nparameters lam;\nlam = -0.5;\n"
    "model;\n  diff(K) = lam * Y;\n  Y = K;\nend;"
)


def test_one_stage_gauss_reproduces_crank_nicolson_pure_ode():
    res = build_residual(build(parse(ODE)))
    cn = crank_nicolson_residual(res)
    coll = collocation_residual(res, gauss(2))

    x_i, x_next, theta, dt, t_i = ca.DM([1.0]), ca.DM([0.8]), ca.DM([-0.5]), 0.1, 0.0
    empty = ca.DM.zeros(0, 1)
    cn_r = float(cn(x_i, x_next, empty, theta, t_i + dt / 2, dt))

    # The single stage derivative consistent with the node update is the
    # difference quotient; the collocation stage residual then equals CN's.
    v = ca.DM([(0.8 - 1.0) / dt])
    out = np.array(coll(x_i, x_next, v, empty, empty, theta, t_i, dt)).reshape(-1)
    assert out.shape == (2,)  # one stage residual + the node update
    assert out[1] == pytest.approx(0.0)  # node update satisfied by construction
    assert out[0] == pytest.approx(cn_r)


def test_residual_shape_with_algebraic_variable():
    res = build_residual(build(parse(DAE)))
    tab = lobatto_iiia(4)
    coll = collocation_residual(res, tab)
    s, n, n_dyn, n_alg = tab.stages, 2, 1, 1
    out = coll(
        ca.DM([1.0, 1.0]),  # x_i
        ca.DM([1.0, 1.0]),  # x_next
        ca.DM.zeros(n_dyn * s, 1),  # V
        ca.DM.zeros(n_alg * s, 1),  # W
        ca.DM.zeros(0, 1),  # e_stages (no exogenous)
        ca.DM([-0.5]),  # theta
        0.0,  # t_i
        0.1,  # dt
    )
    assert out.shape[0] == s * n + n_dyn


def test_algebraic_rows_pin_the_stage_algebraic_unknown():
    # Changing W must change the residual (the algebraic rows constrain it).
    res = build_residual(build(parse(DAE)))
    tab = radau_iia(3)
    coll = collocation_residual(res, tab)
    s, n_dyn, n_alg = tab.stages, 1, 1

    def residual_at(w: ca.DM) -> np.ndarray:
        out = coll(
            ca.DM([1.0, 1.0]),
            ca.DM([1.0, 1.0]),
            ca.DM.zeros(n_dyn * s, 1),
            w,
            ca.DM.zeros(0, 1),
            ca.DM([-0.5]),
            0.0,
            0.1,
        )
        return np.array(out).reshape(-1)

    zeros = residual_at(ca.DM.zeros(n_alg * s, 1))
    ones = residual_at(ca.DM.ones(n_alg * s, 1))
    assert not np.allclose(zeros, ones)

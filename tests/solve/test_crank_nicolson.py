"""Tests for the Crank–Nicolson per-interval residual."""

from __future__ import annotations

import casadi as ca
import pytest

from continuo.codegen import build_residual
from continuo.ir import build
from continuo.parser import parse
from continuo.solve.disc import crank_nicolson_residual

EMPTY = ca.DM.zeros(0, 1)

# diff(K) = b - K  (dynamic);  Y = a*K  (algebraic). parameters a, b.
LINEAR = """
var(state) K;
var Y;
parameters a, b;
a = 0.5;
b = 2;
model;
  diff(K) = b - K;
  Y = a * K;
end;
"""


def cn(src: str):
    return crank_nicolson_residual(build_residual(build(parse(src))))


def test_interval_residual_values():
    interval = cn(LINEAR)
    # x_i=[K0=1, Y0=0.5], x_next=[K1=2, Y1=1], theta=[a=0.5, b=2], t_mid=0, dt=1
    R = interval(ca.DM([1.0, 0.5]), ca.DM([2.0, 1.0]), EMPTY, ca.DM([0.5, 2.0]), 0.0, 1.0)
    # dynamic row: (K1-K0)/dt - b + (K0+K1)/2 = 1 - 2 + 1.5 = 0.5
    assert float(R[0]) == pytest.approx(0.5)
    # algebraic row at midpoint: (Y0+Y1)/2 - a*(K0+K1)/2 = 0.75 - 0.5*1.5 = 0
    assert float(R[1]) == pytest.approx(0.0)


def test_output_length_is_number_of_equations():
    interval = cn(LINEAR)
    R = interval(ca.DM([1.0, 0.5]), ca.DM([2.0, 1.0]), EMPTY, ca.DM([0.5, 2.0]), 0.0, 1.0)
    assert R.shape == (2, 1)


def test_difference_quotient_only_for_dynamic_variables():
    interval = cn(LINEAR)

    # The dynamic row must depend on dt (it uses (K1-K0)/dt); the algebraic
    # row must not. Compare the residual at two different dt values.
    def args(dt):
        return (ca.DM([1.0, 0.5]), ca.DM([2.0, 1.0]), EMPTY, ca.DM([0.5, 2.0]), 0.0, dt)

    r1 = interval(*args(1.0))
    r2 = interval(*args(2.0))
    assert float(r1[0]) != pytest.approx(float(r2[0]))  # dynamic row changes
    assert float(r1[1]) == pytest.approx(float(r2[1]))  # algebraic row unchanged


def test_crank_nicolson_is_exact_for_a_linear_ode():
    # diff(K) = lam*K has the CN update K1 = K0 (1 + lam dt/2)/(1 - lam dt/2);
    # the dynamic residual must vanish there.
    interval = cn(
        "var(state) K;\nvar Y;\nparameters lam;\nlam = -0.5;\n"
        "model;\n  diff(K) = lam * K;\n  Y = K;\nend;"
    )
    lam, dt, k0 = -0.5, 0.1, 3.0
    k1 = k0 * (1 + lam * dt / 2) / (1 - lam * dt / 2)
    R = interval(ca.DM([k0, k0]), ca.DM([k1, k1]), EMPTY, ca.DM([lam]), 0.0, dt)
    assert float(R[0]) == pytest.approx(0.0, abs=1e-12)


def test_exogenous_evaluated_at_midpoint():
    interval = cn("var(state) K;\nvar Y;\nvarexo u;\nmodel;\n  diff(K) = u - K;\n  Y = K;\nend;")
    # x_i=[0,0], x_next=[0,0], u_mid=2, dt=1: dynamic row = 0 - (u - 0) = -2
    R = interval(ca.DM([0.0, 0.0]), ca.DM([0.0, 0.0]), ca.DM([2.0]), EMPTY, 0.0, 1.0)
    assert float(R[0]) == pytest.approx(-2.0)

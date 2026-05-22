"""Tests for residual and Jacobian assembly.

The residual and Jacobian Functions are evaluated numerically (CasADi
``DM`` inputs in the documented vector order) and checked against values
worked out by hand.
"""

from __future__ import annotations

import casadi as ca
import pytest

from continuo.codegen import build_residual
from continuo.ir import build
from continuo.parser import parse

# states=[K], algebraic=[Y], parameters=[alpha]; no exogenous.
#   r1 = diff(K) - (Y - K)   ;   r2 = Y - K^alpha
SRC = """
var(state) K;
var Y;
parameters alpha;
alpha = 0.5;
model;
  diff(K) = Y - K;
  Y = K^alpha;
end;
"""


def residual():
    return build_residual(build(parse(SRC)))


EMPTY = ca.DM.zeros(0, 1)


# --- residual evaluation --------------------------------------------------


def test_residual_values():
    res = residual()
    # xdot=[dK=1], x=[K=4, Y=2], e=[], theta=[alpha=0.5], t=0
    F = res.function(ca.DM([1.0]), ca.DM([4.0, 2.0]), EMPTY, ca.DM([0.5]), 0.0)
    assert float(F[0]) == pytest.approx(1.0 - (2.0 - 4.0))  # 3
    assert float(F[1]) == pytest.approx(2.0 - 4.0**0.5)  # 0


def test_residual_shape_is_square():
    res = residual()
    assert res.expression.shape == (2, 1)
    assert res.function.size_in("x") == (2, 1)
    assert res.function.size_in("xdot") == (1, 1)  # one dynamic variable


# --- Jacobians ------------------------------------------------------------


def test_jacobian_x():
    res = residual()
    # dF/dx at K=4, Y=2, alpha=0.5:
    #   d r1/dK = 1,  d r1/dY = -1
    #   d r2/dK = -0.5 K^-0.5 = -0.25,  d r2/dY = 1
    jx = res.jacobian_x(ca.DM([1.0]), ca.DM([4.0, 2.0]), EMPTY, ca.DM([0.5]), 0.0)
    assert jx.shape == (2, 2)
    assert float(jx[0, 0]) == pytest.approx(1.0)
    assert float(jx[0, 1]) == pytest.approx(-1.0)
    assert float(jx[1, 0]) == pytest.approx(-0.25)
    assert float(jx[1, 1]) == pytest.approx(1.0)


def test_jacobian_xdot():
    res = residual()
    # dF/d(xdot): only r1 depends on diff(K).
    jd = res.jacobian_xdot(ca.DM([1.0]), ca.DM([4.0, 2.0]), EMPTY, ca.DM([0.5]), 0.0)
    assert jd.shape == (2, 1)
    assert float(jd[0, 0]) == pytest.approx(1.0)
    assert float(jd[1, 0]) == pytest.approx(0.0)


# --- bare equation residual -----------------------------------------------


def test_bare_equation_residual():
    # `diff(K) - Y;` is a bare equation meaning diff(K) - Y == 0.
    model = build(parse("var(state) K;\nvar Y;\nmodel;\n  diff(K) - Y;\n  Y = K;\nend;"))
    res = build_residual(model)
    # xdot=[dK=3], x=[K=5, Y=2] -> r1 = 3 - 2 = 1
    F = res.function(ca.DM([3.0]), ca.DM([5.0, 2.0]), EMPTY, EMPTY, 0.0)
    assert float(F[0]) == pytest.approx(1.0)


# --- exogenous and time dependence ----------------------------------------


def test_exogenous_enters_residual():
    model = build(
        parse("var(state) K;\nvar Y;\nvarexo eps;\nmodel;\n  diff(K) = Y + eps;\n  Y = K;\nend;")
    )
    res = build_residual(model)
    assert res.function.size_in("e") == (1, 1)
    # xdot=[dK=0], x=[K=1, Y=1], e=[eps=0.5] -> r1 = 0 - (1 + 0.5) = -1.5
    F = res.function(ca.DM([0.0]), ca.DM([1.0, 1.0]), ca.DM([0.5]), EMPTY, 0.0)
    assert float(F[0]) == pytest.approx(-1.5)


def test_time_dependence():
    model = build(parse("var(state) K;\nvar Y;\nmodel;\n  diff(K) = Y;\n  Y = t;\nend;"))
    res = build_residual(model)
    # r2 = Y - t; at Y=3, t=2 -> 1
    F = res.function(ca.DM([0.0]), ca.DM([0.0, 3.0]), EMPTY, EMPTY, 2.0)
    assert float(F[1]) == pytest.approx(1.0)


# --- empty vectors --------------------------------------------------------


def test_no_parameters_or_exogenous():
    model = build(parse("var(state) K;\nvar Y;\nmodel;\n  diff(K) = Y;\n  Y = K;\nend;"))
    res = build_residual(model)
    assert res.function.size_in("e") == (0, 1)
    assert res.function.size_in("theta") == (0, 1)
    F = res.function(ca.DM([2.0]), ca.DM([5.0, 5.0]), EMPTY, EMPTY, 0.0)
    assert float(F[0]) == pytest.approx(2.0 - 5.0)  # diff(K) - Y = -3


# --- higher-order auxiliaries flow through --------------------------------


def test_higher_order_model_assembles():
    # diff(x, 2) introduces __aux_diff_x_1; the reduced model is square.
    model = build(parse("var(state) x;\nvar Y;\nmodel;\n  diff(x, 2) = Y - x;\n  Y = x;\nend;"))
    res = build_residual(model)
    assert res.expression.shape[0] == len(model.endogenous)  # square
    assert res.function.size_in("xdot") == (2, 1)  # x and its auxiliary

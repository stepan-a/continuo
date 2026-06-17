"""Tests for the change-of-variable module (solve/transform.py)."""

from __future__ import annotations

import casadi as ca
import numpy as np
import pytest

from continuo.ir import build
from continuo.parser import parse
from continuo.solve import SolveError
from continuo.solve.steady import evaluate_parameters
from continuo.solve.transform import (
    VarTransform,
    build_constrained_problem,
    build_transforms,
)

LOWER = VarTransform("K", 2.0, None)
UPPER = VarTransform("X", None, 5.0)
BOTH = VarTransform("u", 0.0, 1.0)
NONE = VarTransform("z", None, None)


# --- round trip -----------------------------------------------------------


@pytest.mark.parametrize("transform", [LOWER, UPPER, BOTH, NONE])
@pytest.mark.parametrize("y", [-3.0, -0.5, 0.0, 0.7, 4.0])
def test_inverse_undoes_forward(transform, y):
    assert transform.inverse(transform.forward(y)) == pytest.approx(y)


@pytest.mark.parametrize("transform", [LOWER, UPPER, BOTH])
@pytest.mark.parametrize("y", [-8.0, 0.0, 8.0])
def test_forward_image_strictly_in_domain(transform, y):
    x = transform.forward(y)
    if transform.lower is not None:
        assert x > transform.lower
    if transform.upper is not None:
        assert x < transform.upper


# --- default interior -----------------------------------------------------


def test_default_interior_lower():
    assert LOWER.default_interior() == pytest.approx(3.0)  # a + exp(0)


def test_default_interior_upper():
    assert UPPER.default_interior() == pytest.approx(4.0)  # b - exp(0)


def test_default_interior_both_is_midpoint():
    assert BOTH.default_interior() == pytest.approx(0.5)


# --- inverse domain errors ------------------------------------------------


def test_inverse_on_lower_bound_rejected():
    with pytest.raises(SolveError, match="strictly interior"):
        LOWER.inverse(2.0)


def test_inverse_below_lower_rejected():
    with pytest.raises(SolveError, match="outside"):
        LOWER.inverse(1.0)


def test_inverse_outside_interval_rejected():
    with pytest.raises(SolveError, match="open interval"):
        BOTH.inverse(1.5)


def test_inverse_on_upper_bound_rejected():
    with pytest.raises(SolveError):
        UPPER.inverse(5.0)


# --- forward_sx agrees with forward ---------------------------------------


@pytest.mark.parametrize("transform", [LOWER, UPPER, BOTH, NONE])
@pytest.mark.parametrize("y", [-2.0, 0.0, 1.3])
def test_forward_sx_matches_forward(transform, y):
    y_sx = ca.SX.sym("y")
    f = ca.Function("f", [y_sx], [transform.forward_sx(y_sx)])
    assert float(f(y)) == pytest.approx(transform.forward(y))


# --- build_transforms -----------------------------------------------------

POWER = """
var(state, positive) K;
var(boundaries=(0, kmax)) Y;
var W;
parameters kmax;
kmax = 100;
model;
  diff(K) = Y - K;
  Y = K;
  W = K;
end;
"""


def test_build_transforms_aligned_with_endogenous():
    m = build(parse(POWER))
    theta = evaluate_parameters(m)
    transforms = build_transforms(m, theta, {})
    assert [t.name for t in transforms] == list(m.endogenous)


def test_build_transforms_identity_for_unconstrained():
    m = build(parse(POWER))
    transforms = {t.name: t for t in build_transforms(m, evaluate_parameters(m), {})}
    assert transforms["W"].lower is None and transforms["W"].upper is None
    assert not transforms["W"].constrained


def test_build_transforms_evaluates_parameter_bound():
    m = build(parse(POWER))
    transforms = {t.name: t for t in build_transforms(m, evaluate_parameters(m), {})}
    assert transforms["Y"].upper == pytest.approx(100.0)


def test_build_transforms_empty_parameter_domain_rejected():
    src = POWER.replace("kmax = 100;", "kmax = -1;")
    m = build(parse(src))
    with pytest.raises(SolveError, match="empty domain"):
        build_transforms(m, evaluate_parameters(m), {})


# --- build_constrained_problem --------------------------------------------


def test_constrained_problem_residual_uses_transformed_x():
    # F(y) must equal F(T(y)) of the underlying model residual.
    m = build(parse(POWER))
    theta = evaluate_parameters(m)
    transforms = build_transforms(m, theta, {})
    from continuo.codegen.residual import build_residual

    residual = build_residual(m)
    xdot_zero = ca.DM.zeros(len(m.states) + len(m.jumps), 1)
    theta_vec = ca.DM([theta[p] for p in m.parameters])
    e_vec = ca.DM.zeros(0, 1)
    y0 = np.zeros(len(transforms))
    problem, untransform = build_constrained_problem(
        residual, xdot_zero, e_vec, theta_vec, transforms, y0
    )
    y = np.array([0.3, -0.2, 1.1])
    x = untransform(y)
    # Each x component is strictly inside its domain.
    assert x[0] > 0 and 0 < x[1] < 100
    # The y-residual equals the x-residual at x = T(y).
    f_x = np.array(residual.function(xdot_zero, ca.DM(x), e_vec, theta_vec, 0.0)).reshape(-1)
    assert problem.g(y) == pytest.approx(f_x)


def test_constrained_problem_jacobian_carries_chain_rule():
    # ∂F/∂y should match a finite-difference of g in y (validates AD chain rule).
    m = build(parse(POWER))
    theta = evaluate_parameters(m)
    transforms = build_transforms(m, theta, {})
    from continuo.codegen.residual import build_residual

    residual = build_residual(m)
    xdot_zero = ca.DM.zeros(len(m.states) + len(m.jumps), 1)
    theta_vec = ca.DM([theta[p] for p in m.parameters])
    e_vec = ca.DM.zeros(0, 1)
    y0 = np.zeros(len(transforms))
    problem, _ = build_constrained_problem(residual, xdot_zero, e_vec, theta_vec, transforms, y0)
    y = np.array([0.4, 0.1, -0.3])
    analytic = problem.jac(y)
    eps = 1e-6
    fd = np.empty_like(analytic)
    for j in range(len(y)):
        yp, ym = y.copy(), y.copy()
        yp[j] += eps
        ym[j] -= eps
        fd[:, j] = (problem.g(yp) - problem.g(ym)) / (2 * eps)
    assert analytic == pytest.approx(fd, abs=1e-5)

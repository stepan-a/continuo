"""Tests for the steady-state solver."""

from __future__ import annotations

import pytest

from continuo.ir import build
from continuo.parser import parse
from continuo.solve import SolveError, evaluate_parameters, steady_state


def model(src: str):
    return build(parse(src))


# A linear model with a closed-form SS: K* = b, Y* = a*b.
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


# --- parameter evaluation -------------------------------------------------


def test_evaluate_parameters_literal():
    theta = evaluate_parameters(model("parameters a, b;\na = 0.5;\nb = 2;"))
    assert theta == {"a": 0.5, "b": 2.0}


def test_evaluate_parameters_expression_referencing_earlier():
    theta = evaluate_parameters(model("parameters rho, beta;\nrho = 0.02;\nbeta = 1 / (1 + rho);"))
    assert theta["beta"] == pytest.approx(1 / 1.02)


def test_missing_parameter_value_rejected():
    with pytest.raises(SolveError, match="parameter 'beta' has no value"):
        evaluate_parameters(model("parameters alpha, beta;\nalpha = 0.3;"))


# --- numerical steady state -----------------------------------------------


def test_numerical_steady_state():
    ss = steady_state(model(LINEAR))
    assert ss["K"] == pytest.approx(2.0)
    assert ss["Y"] == pytest.approx(1.0)


def test_numerical_with_exogenous():
    src = "var(state) K;\nvar Y;\nvarexo eps;\nmodel;\n  diff(K) = eps - K;\n  Y = K;\nend;"
    ss = steady_state(model(src), exogenous={"eps": 3.0})
    assert ss["K"] == pytest.approx(3.0)  # K* = eps
    assert ss["Y"] == pytest.approx(3.0)


def test_singular_jacobian_rejected():
    # diff(K) = 1 has no steady state (and a singular SS Jacobian).
    src = "var(state) K;\nvar Y;\nmodel;\n  diff(K) = 1;\n  Y = K;\nend;"
    with pytest.raises(SolveError):
        steady_state(model(src))


def test_non_convergence_rejected():
    src = LINEAR
    with pytest.raises(SolveError, match="did not converge"):
        steady_state(model(src), max_iter=0)


def test_initial_guess_is_used():
    # A power-law model where Newton from 1.0 struggles but a good guess works.
    src = (
        "var(state) K;\nvar Y;\nparameters alpha, delta;\n"
        "alpha = 0.3;\ndelta = 0.1;\n"
        "model;\n  diff(K) = Y - delta * K;\n  Y = K^alpha;\nend;\n"
        "initial_guess;\n  K = 25;\n  Y = 2.5;\nend;"
    )
    ss = steady_state(model(src))
    # SS: K^alpha = delta*K  ->  K = delta^(1/(alpha-1)) = 0.1^(1/-0.7)
    assert ss["K"] == pytest.approx(0.1 ** (1 / (0.3 - 1)), rel=1e-6)


# --- analytical steady state ----------------------------------------------


def test_analytical_steady_state():
    src = LINEAR + "steady_state_model;\n  K = b;\n  Y = a * b;\nend;"
    ss = steady_state(model(src))
    assert ss["K"] == pytest.approx(2.0)
    assert ss["Y"] == pytest.approx(1.0)


def test_analytical_matches_numerical():
    src = (
        "var(state) K;\nvar Y;\nparameters alpha, delta;\n"
        "alpha = 0.3;\ndelta = 0.1;\n"
        "model;\n  diff(K) = Y - delta * K;\n  Y = K^alpha;\nend;\n"
        "steady_state_model;\n  K = delta^(1 / (alpha - 1));\n  Y = delta * K;\nend;"
    )
    analytical = steady_state(model(src))
    # Numerical from the analytical values must reproduce them.
    numerical = steady_state(model(src.split("steady_state_model")[0]), guess=analytical)
    assert numerical["K"] == pytest.approx(analytical["K"], rel=1e-6)
    assert numerical["Y"] == pytest.approx(analytical["Y"], rel=1e-6)


def test_analytical_uses_exogenous_on_rhs():
    src = (
        "var(state) K;\nvar Y;\nvarexo a;\n"
        "model;\n  diff(K) = a - K;\n  Y = K;\nend;\n"
        "steady_state_model;\n  K = a;\n  Y = a;\nend;"
    )
    ss = steady_state(model(src), exogenous={"a": 4.0})
    assert ss["K"] == pytest.approx(4.0)


def test_higher_order_auxiliary_steady_state_is_zero():
    src = (
        "var(state) x;\nvar Y;\n"
        "model;\n  diff(x, 2) = Y - x;\n  Y = x;\nend;\n"
        "steady_state_model;\n  x = 0;\n  Y = 0;\nend;"
    )
    ss = steady_state(model(src))
    assert ss["__aux_diff_x_1"] == pytest.approx(0.0)

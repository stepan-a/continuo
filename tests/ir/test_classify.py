"""Tests for the variable-classification pass.

``build`` runs classification automatically once a model carries
equations, so a valid model builds without error and an inconsistent one
raises :class:`IRError`. The pass is also exercised directly via
``classify`` for the declarations-only edge case.
"""

from __future__ import annotations

import pytest

from dynare_ct.ir import IRError, build, classify
from dynare_ct.parser import parse

# A small but complete model: one state (K), one jump (C), one algebraic (Y).
RBC = """
var(state) K;
var(jump) C;
var Y;
varexo eps;
parameters alpha;
alpha = 0.33;
model;
  diff(K) = Y - C;
  diff(C) = C * (Y - alpha);
  Y = K^alpha + eps;
end;
"""


def ir(src: str):
    return build(parse(src))


# --- valid models ---------------------------------------------------------


def test_well_formed_model_passes():
    m = ir(RBC)
    assert m.states == ("K",) and m.jumps == ("C",) and m.algebraic == ("Y",)


def test_higher_order_diff_counts_as_dynamic():
    # diff(K, 2) still differentiates K; first-order reduction is a later pass.
    ir("var(state) K;\nvar Y;\nmodel;\n  diff(K, 2) = Y;\n  Y = K;\nend;")


def test_nested_diff_counts_as_dynamic():
    ir("var(state) K;\nvar Y;\nmodel;\n  diff(diff(K)) = Y;\n  Y = K;\nend;")


def test_diff_of_expression_with_state_and_parameter():
    # The subject must be a bare variable; diff(K) here, alpha is a coefficient.
    ir(
        "var(state) K;\nvar Y;\nparameters alpha;\nalpha = 0.3;\n"
        "model;\n  alpha * diff(K) = Y;\n  Y = K;\nend;"
    )


# --- missing / misplaced derivatives --------------------------------------


def test_state_without_derivative_rejected():
    with pytest.raises(IRError, match="state 'K' is declared but its time derivative"):
        ir("var(state) K;\nvar Y;\nmodel;\n  K = Y;\n  Y = 1;\nend;")


def test_jump_without_derivative_rejected():
    with pytest.raises(IRError, match="jump 'C' is declared"):
        ir("var(jump) C;\nvar Y;\nmodel;\n  C = Y;\n  Y = 1;\nend;")


def test_algebraic_with_derivative_rejected():
    with pytest.raises(IRError, match="declared algebraic but its time derivative"):
        ir("var Y;\nvar(state) K;\nmodel;\n  diff(Y) = K;\n  diff(K) = Y;\nend;")


def test_diff_of_exogenous_rejected():
    with pytest.raises(IRError, match="exogenous variable 'eps'"):
        ir("var(state) K;\nvarexo eps;\nmodel;\n  diff(eps) = K;\n  diff(K) = eps;\nend;")


def test_diff_of_parameter_rejected():
    with pytest.raises(IRError, match="parameter 'alpha'"):
        ir(
            "var(state) K;\nparameters alpha;\nalpha = 1;\n"
            "model;\n  diff(alpha) = K;\n  diff(K) = alpha;\nend;"
        )


def test_diff_of_undeclared_rejected():
    with pytest.raises(IRError, match="undeclared variable 'Z'"):
        ir("var(state) K;\nmodel;\n  diff(Z) = K;\n  diff(K) = 1;\nend;")


def test_diff_of_non_variable_rejected():
    with pytest.raises(IRError, match="diff.. expects a variable"):
        ir("var(state) K;\nvar Y;\nmodel;\n  diff(K + Y) = 0;\n  Y = K;\nend;")


# --- counts ---------------------------------------------------------------


def test_non_square_system_rejected():
    # Two endogenous (K, Y) but three equations.
    with pytest.raises(IRError, match="3 equation.* but 2 endogenous"):
        ir("var(state) K;\nvar Y;\nmodel;\n  diff(K) = Y;\n  Y = K;\n  Y = 1;\nend;")


def test_too_many_dynamic_equations_rejected():
    # K is the only dynamic variable, but two equations carry diff(K).
    with pytest.raises(IRError, match="expected 1 dynamic equation.* but found 2"):
        ir("var(state) K;\nvar Y;\nmodel;\n  diff(K) = Y;\n  diff(K) = Y + 1;\nend;")


# --- over-determination ---------------------------------------------------


def test_overdetermined_variable_rejected():
    # K is both pinned by `K = Y` and evolved by `diff(K)`.
    with pytest.raises(IRError, match="over-determined"):
        ir("var(state) K;\nvar Y;\nmodel;\n  diff(K) = Y;\n  K = Y;\nend;")


# --- standalone classify --------------------------------------------------


def test_classify_rejects_declarations_only_model():
    # build() skips classification without equations, but calling it
    # directly treats the file as a (non-square) whole model.
    m = build(parse("var Y;"))
    with pytest.raises(IRError, match="0 equation"):
        classify(m)


def test_declarations_only_still_builds():
    # The shared-fragment case: declarations without equations is fine.
    m = ir("parameters alpha, beta;\nalpha = 0.33;")
    assert m.parameters == ("alpha", "beta")

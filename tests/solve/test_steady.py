"""Tests for the steady-state solver."""

from __future__ import annotations

import pytest

from continuo.ir import build
from continuo.parser import parse
from continuo.solve import SolveError, directive_solver, evaluate_parameters, steady_state


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
    # A per-iteration cap of 0 starves Newton; the explicit backend cannot
    # fall through to the auto chain, so the failure surfaces.
    src = LINEAR
    with pytest.raises(SolveError, match="did not converge"):
        steady_state(model(src), solver="newton", max_iter=0)


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


def test_solver_choice_matches_default():
    src = (
        "var(state) K;\nvar Y;\nparameters alpha, delta;\n"
        "alpha = 0.3;\ndelta = 0.1;\n"
        "model;\n  diff(K) = Y - delta * K;\n  Y = K^alpha;\nend;\n"
        "initial_guess;\n  K = 25;\n  Y = 2.5;\nend;"
    )
    expected = steady_state(model(src))["K"]
    for solver in ("newton", "hybr", "homotopy"):
        assert steady_state(model(src), solver=solver)["K"] == pytest.approx(expected, rel=1e-8)


# --- the steady directive's solver ----------------------------------------


def test_directive_solver_reads_the_steady_directive():
    assert directive_solver(model(LINEAR + "steady(solver=hybr);")) == "hybr"


def test_directive_solver_is_none_when_absent():
    assert directive_solver(model(LINEAR)) is None


# --- constrained steady state (change of variable) ------------------------

# A power-law model whose economically meaningful root is interior:
# diff(K) = Y - delta*K, Y = K^alpha  ->  K = delta^(1/(alpha-1)) ~ 26.8.
# It also has a spurious root at K = 0 that the unconstrained solve drifts
# to from the default guess; bounding K away from 0 steers to the real one.
CONSTRAINED = (
    "var(state, boundaries=(0.5, 1000)) K;\n"
    "var(positive) Y;\n"
    "parameters alpha, delta;\n"
    "alpha = 0.3;\ndelta = 0.1;\n"
    "model;\n  diff(K) = Y - delta * K;\n  Y = K^alpha;\nend;\n"
)
K_STAR = 0.1 ** (1 / (0.3 - 1))


def test_constrained_converges_without_initial_guess():
    # The phare: bounds alone steer the default-guess solve to the analytical
    # value, with no initial_guess block.
    ss = steady_state(model(CONSTRAINED))
    assert ss["K"] == pytest.approx(K_STAR, rel=1e-6)
    assert ss["Y"] == pytest.approx(K_STAR**0.3, rel=1e-6)


def test_unconstrained_same_model_misses_the_interior_root():
    # Without the constraint, the default guess drifts to the K≈0 root.
    src = CONSTRAINED.replace("(state, boundaries=(0.5, 1000))", "(state)").replace(
        "var(positive) Y;", "var Y;"
    )
    assert steady_state(model(src))["K"] != pytest.approx(K_STAR, rel=1e-3)


def test_constrained_one_sided_lower_bound():
    # K^alpha = 2  ->  K = 2^(1/alpha); a unique positive root, no K=0 root.
    src = (
        "var(state, positive) K;\nvar Y;\nparameters alpha;\nalpha = 0.3;\n"
        "model;\n  diff(K) = 2 - Y;\n  Y = K^alpha;\nend;"
    )
    assert steady_state(model(src))["K"] == pytest.approx(2 ** (1 / 0.3), rel=1e-6)


def test_constrained_parameter_bound():
    src = (
        CONSTRAINED.replace("boundaries=(0.5, 1000)", "boundaries=(0.5, kmax)")
        .replace("parameters alpha, delta;", "parameters alpha, delta, kmax;")
        .replace("delta = 0.1;", "delta = 0.1;\nkmax = 1000;")
    )
    assert steady_state(model(src))["K"] == pytest.approx(K_STAR, rel=1e-6)


def test_constrained_guess_out_of_domain_rejected():
    with pytest.raises(SolveError, match="outside"):
        steady_state(model(CONSTRAINED), guess={"K": 2000.0})


def test_constraints_are_inert_with_analytical_steady_state():
    # An analytical steady_state_model wins; the constraints are validated
    # but unused (closed form, no change of variable).
    src = CONSTRAINED + (
        "steady_state_model;\n  K = delta^(1 / (alpha - 1));\n  Y = K^alpha;\nend;"
    )
    ss = steady_state(model(src))
    assert ss["K"] == pytest.approx(K_STAR, rel=1e-12)


@pytest.mark.parametrize("solver", ["newton", "hybr", "kinsol"])
def test_constrained_across_backends(solver):
    # Each backend must solve in y-space and recover K*; an initial_guess
    # isolates "the change of variable composes with this backend" from the
    # harder question of robustness from a far midpoint start.
    from continuo.solve.rootfind import available_steady_solvers

    if solver not in available_steady_solvers():
        pytest.skip(f"{solver} backend unavailable")
    src = CONSTRAINED + "initial_guess;\n  K = 20;\n  Y = 2.5;\nend;"
    ss = steady_state(model(src), solver=solver)
    assert ss["K"] == pytest.approx(K_STAR, rel=1e-6)


# --- the nodomain flag ----------------------------------------------------


def test_nodomain_solves_in_raw_x():
    # With nodomain the change of variable is skipped, so the same default
    # guess that lands on K* under constraints drifts to the spurious root.
    constrained = steady_state(model(CONSTRAINED))["K"]
    raw = steady_state(model(CONSTRAINED), nodomain=True)["K"]
    assert constrained == pytest.approx(K_STAR, rel=1e-6)
    assert raw != pytest.approx(K_STAR, rel=1e-3)


def test_nodomain_ignores_out_of_domain_guess():
    # The guess validation belongs to the change of variable; nodomain skips
    # it, so a guess outside the declared domain is accepted in raw x.
    ss = steady_state(model(CONSTRAINED), nodomain=True, guess={"K": 20.0, "Y": 2.5})
    assert ss["K"] == pytest.approx(K_STAR, rel=1e-6)


def test_directive_nodomain_reads_the_flag():
    from continuo.solve import directive_nodomain

    assert directive_nodomain(model(CONSTRAINED + "steady(nodomain);")) is True
    assert directive_nodomain(model(CONSTRAINED + "steady;")) is False


def test_higher_order_auxiliary_steady_state_is_zero():
    src = (
        "var(state) x;\nvar Y;\n"
        "model;\n  diff(x, 2) = Y - x;\n  Y = x;\nend;\n"
        "steady_state_model;\n  x = 0;\n  Y = 0;\nend;"
    )
    ss = steady_state(model(src))
    assert ss["__aux_diff_x_1"] == pytest.approx(0.0)

"""Tests for the real-math builtin function library."""

from __future__ import annotations

import math

import pytest

from dynare_ct.macro.eval import MacroError, evaluate


def ev(text: str, **env):
    return evaluate(text, env)


# --- transcendental (always return a real) --------------------------------


@pytest.mark.parametrize(
    "expr,expected",
    [
        ("exp(0)", 1.0),
        ("ln(1)", 0.0),
        ("log(1)", 0.0),
        ("log10(1000)", 3.0),
        ("sqrt(9)", 3.0),
        ("sin(0)", 0.0),
        ("cos(0)", 1.0),
        ("atan(0)", 0.0),
    ],
)
def test_unary_real_functions(expr, expected):
    result = ev(expr)
    assert isinstance(result, float)
    assert result == pytest.approx(expected)


def test_exp_ln_roundtrip():
    assert ev("ln(exp(2))") == pytest.approx(2.0)


def test_domain_error_maps_to_macroerror():
    with pytest.raises(MacroError, match="sqrt"):
        ev("sqrt(-1)")
    with pytest.raises(MacroError, match="ln"):
        ev("ln(0)")


# --- rounding family (return integers) ------------------------------------


@pytest.mark.parametrize(
    "expr,expected",
    [
        ("floor(2.7)", 2),
        ("ceil(2.1)", 3),
        ("trunc(2.9)", 2),
        ("trunc(-2.9)", -2),
        ("round(2.5)", 3),
        ("round(-2.5)", -3),
        ("round(2.4)", 2),
        ("sign(-5)", -1),
        ("sign(0)", 0),
        ("sign(42)", 1),
    ],
)
def test_rounding_returns_int(expr, expected):
    result = ev(expr)
    assert isinstance(result, int)
    assert result == expected


def test_rounding_results_are_usable_as_indices():
    assert ev("v[floor(2.9)]", v=[10, 20, 30]) == 20


# --- abs preserves type ---------------------------------------------------


def test_abs_preserves_int_and_float():
    assert ev("abs(-3)") == 3
    assert isinstance(ev("abs(-3)"), int)
    assert ev("abs(-3.5)") == pytest.approx(3.5)
    assert isinstance(ev("abs(-3.5)"), float)


# --- mod / power ----------------------------------------------------------


@pytest.mark.parametrize(
    "expr,expected",
    [
        ("mod(7, 3)", 1),
        ("mod(-7, 3)", 2),  # divisor sign, like MATLAB
        ("mod(7, -3)", -2),
        ("power(2, 10)", 1024),
    ],
)
def test_mod_and_power(expr, expected):
    assert ev(expr) == expected


def test_mod_int_stays_int():
    assert isinstance(ev("mod(7, 3)"), int)


def test_mod_by_zero_raises():
    with pytest.raises(MacroError, match="mod.. by zero"):
        ev("mod(1, 0)")


# --- min / max ------------------------------------------------------------


def test_min_max_variadic():
    assert ev("min(3, 1, 2)") == 1
    assert ev("max(3, 1, 2)") == 3


def test_min_max_over_array():
    assert ev("min(v)", v=[5, 2, 8]) == 2
    assert ev("max(v)", v=[5, 2, 8]) == 8


def test_min_preserves_int():
    assert isinstance(ev("min(3, 1)"), int)


def test_max_of_empty_raises():
    with pytest.raises(MacroError, match="empty"):
        ev("max(v)", v=[])


# --- normal distribution --------------------------------------------------


def test_normpdf_standard():
    assert ev("normpdf(0)") == pytest.approx(1.0 / math.sqrt(2 * math.pi))


def test_normcdf_standard():
    assert ev("normcdf(0)") == pytest.approx(0.5)
    assert ev("normcdf(-100)") == pytest.approx(0.0, abs=1e-12)
    assert ev("normcdf(100)") == pytest.approx(1.0)


def test_normcdf_with_mean_and_sd():
    assert ev("normcdf(5, 5, 2)") == pytest.approx(0.5)


def test_norm_rejects_nonpositive_sigma():
    with pytest.raises(MacroError, match="sigma must be positive"):
        ev("normpdf(0, 0, 0)")


def test_norm_wrong_arity():
    with pytest.raises(MacroError, match="1 or 3"):
        ev("normcdf(1, 2)")


# --- argument validation --------------------------------------------------


def test_numeric_function_rejects_non_numbers():
    with pytest.raises(MacroError, match="numeric"):
        ev('sqrt("x")')


def test_wrong_arity_for_unary():
    with pytest.raises(MacroError, match="expects 1 argument"):
        ev("exp(1, 2)")


def test_functions_compose_with_operators():
    assert ev("floor(sqrt(50)) + 1") == 8


def test_function_in_macro_context_via_evaluate():
    # sanity: builtins are usable anywhere evaluate() is called
    assert ev("max(alpha, 0.5)", alpha=0.3) == pytest.approx(0.5)

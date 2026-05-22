"""Tests for lowering model expressions to CasADi.

Each translated expression is wrapped in a CasADi Function and evaluated
numerically, so the tests check that the lowering computes the right thing
rather than inspecting symbolic structure.
"""

from __future__ import annotations

import casadi as ca
import pytest

from dynare_ct.codegen import CodegenError, build_symbols, translate
from dynare_ct.codegen.translate import SymbolTable
from dynare_ct.parser import parse
from dynare_ct.parser.ast import ParameterValue


def expr_of(text: str):
    stmt = parse(f"q = {text};").statements[0]
    assert isinstance(stmt, ParameterValue)
    return stmt.value


def evaluate(text: str, values: dict[str, float], derivatives: dict[str, float] | None = None):
    """Translate ``text`` and evaluate it with the given symbol values."""
    derivatives = derivatives or {}
    symbols = {name: ca.SX.sym(name) for name in values}
    symbols.setdefault("t", ca.SX.sym("t"))
    der_syms = {name: ca.SX.sym(f"d_{name}") for name in derivatives}
    table = SymbolTable(symbols, der_syms)

    result = translate(expr_of(text), table)

    symbol_items = list(symbols.items())
    der_items = list(der_syms.items())
    args = [sx for _, sx in symbol_items] + [sx for _, sx in der_items]
    vals = [values.get(name, 0.0) for name, _ in symbol_items] + [
        derivatives[name] for name, _ in der_items
    ]
    func = ca.Function("f", args, [result])
    return float(func(*vals))


# --- atoms and arithmetic -------------------------------------------------


def test_number_literal():
    assert evaluate("42", {}) == 42.0


def test_variable():
    assert evaluate("x", {"x": 3.0}) == 3.0


def test_arithmetic():
    assert evaluate("2 * x + 3", {"x": 4.0}) == 11.0


def test_power():
    assert evaluate("x ^ 3", {"x": 2.0}) == 8.0


def test_division():
    assert evaluate("x / y", {"x": 7.0, "y": 2.0}) == pytest.approx(3.5)


def test_unary_minus():
    assert evaluate("-x", {"x": 5.0}) == -5.0


def test_parameter_and_variable_mix():
    assert evaluate("alpha * x", {"alpha": 0.5, "x": 4.0}) == 2.0


# --- functions ------------------------------------------------------------


@pytest.mark.parametrize(
    "text,values,expected",
    [
        ("exp(x)", {"x": 0.0}, 1.0),
        ("ln(x)", {"x": 1.0}, 0.0),
        ("log(x)", {"x": 1.0}, 0.0),
        ("log10(x)", {"x": 1000.0}, 3.0),
        ("sqrt(x)", {"x": 9.0}, 3.0),
        ("sin(x)", {"x": 0.0}, 0.0),
        ("cos(x)", {"x": 0.0}, 1.0),
        ("abs(x)", {"x": -4.0}, 4.0),
        ("sign(x)", {"x": -3.0}, -1.0),
        ("erf(x)", {"x": 0.0}, 0.0),
    ],
)
def test_unary_functions(text, values, expected):
    assert evaluate(text, values) == pytest.approx(expected)


def test_exp_log_compose():
    assert evaluate("ln(exp(x))", {"x": 2.5}) == pytest.approx(2.5)


def test_min_and_max():
    assert evaluate("min(x, y)", {"x": 3.0, "y": 5.0}) == 3.0
    assert evaluate("max(x, y)", {"x": 3.0, "y": 5.0}) == 5.0


def test_min_max_variadic():
    assert evaluate("max(x, y, 7)", {"x": 3.0, "y": 5.0}) == 7.0


# --- conditionals ---------------------------------------------------------


def test_if_two_branches():
    assert evaluate("if(x > 0, 1, 2)", {"x": 5.0}) == 1.0
    assert evaluate("if(x > 0, 1, 2)", {"x": -5.0}) == 2.0


def test_if_one_branch_sugar():
    assert evaluate("if(x >= 1, x)", {"x": 3.0}) == 3.0
    assert evaluate("if(x >= 1, x)", {"x": 0.0}) == 0.0  # else defaults to 0


def test_logical_and_in_condition():
    assert evaluate("if((x > 0) && (y > 0), 1, 0)", {"x": 1.0, "y": 1.0}) == 1.0
    assert evaluate("if((x > 0) && (y > 0), 1, 0)", {"x": 1.0, "y": -1.0}) == 0.0


# --- time derivatives -----------------------------------------------------


def test_diff_resolves_to_derivative_symbol():
    assert evaluate("diff(x)", {"x": 1.0}, derivatives={"x": 0.7}) == pytest.approx(0.7)


def test_diff_in_expression():
    # diff(K) - I, with d/dt K = 2 and I = 0.5  ->  1.5
    assert evaluate("diff(K) - I", {"K": 1.0, "I": 0.5}, derivatives={"K": 2.0}) == pytest.approx(
        1.5
    )


def test_diff_without_derivative_symbol_errors():
    with pytest.raises(CodegenError, match="no time derivative defined for 'x'"):
        evaluate("diff(x)", {"x": 1.0})  # no derivative provided


# --- errors ---------------------------------------------------------------


def test_unknown_symbol_errors():
    with pytest.raises(CodegenError, match="unknown symbol 'z'"):
        evaluate("z + 1", {"x": 1.0})


def test_unknown_function_errors():
    with pytest.raises(CodegenError, match="unknown function 'frobnicate'"):
        evaluate("frobnicate(x)", {"x": 1.0})


def test_string_literal_errors():
    with pytest.raises(CodegenError, match="string literal"):
        evaluate('x + "a"', {"x": 1.0})


def test_unary_arity_error():
    with pytest.raises(CodegenError, match="exactly one argument"):
        evaluate("exp(x, y)", {"x": 1.0, "y": 2.0})


# --- build_symbols --------------------------------------------------------


def test_build_symbols_covers_the_model():
    from dynare_ct.ir import build

    model = build(
        parse(
            "var(state) K;\nvar Y;\nvarexo eps;\nparameters alpha;\nalpha = 0.3;\n"
            "model;\n  diff(K) = Y - K + eps;\n  Y = K^alpha;\nend;"
        )
    )
    table = build_symbols(model)
    assert set(table.symbols) == {"K", "Y", "eps", "alpha", "t"}
    assert set(table.derivatives) == {"K"}  # only the state has a derivative


def test_translate_a_real_equation_residual():
    from dynare_ct.ir import build

    model = build(
        parse(
            "var(state) K;\nvar Y;\nparameters alpha;\nalpha = 0.5;\n"
            "model;\n  diff(K) = Y - K;\n  Y = K^alpha;\nend;"
        )
    )
    table = build_symbols(model)
    # Residual of `Y = K^alpha`  ->  Y - K^alpha.
    eq = model.equations[1]
    residual = translate(eq.lhs, table) - translate(eq.rhs, table)
    args = [table.symbols[n] for n in ("Y", "K", "alpha")]
    func = ca.Function("r", args, [residual])
    # Y=2, K=9, alpha=0.5  ->  2 - 3 = -1
    assert float(func(2.0, 9.0, 0.5)) == pytest.approx(-1.0)

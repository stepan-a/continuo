"""Tests for parsing declaration statements (var, varexo, parameters)."""

from __future__ import annotations

import pytest

from continuo.parser import parse
from continuo.parser.ast import (
    ParameterDecl,
    ParameterValue,
    VarDecl,
    VarexoDecl,
    VarKind,
)
from continuo.parser.errors import LarkError

# --- valid: var declarations ----------------------------------------------


def test_var_algebraic_default():
    model = parse("var Y, r, w;")
    assert len(model.statements) == 1
    decl = model.statements[0]
    assert isinstance(decl, VarDecl)
    assert decl.kind is VarKind.ALGEBRAIC
    assert [n.name for n in decl.names] == ["Y", "r", "w"]


def test_var_state():
    decl = parse("var(state) K, A;").statements[0]
    assert isinstance(decl, VarDecl)
    assert decl.kind is VarKind.STATE
    assert [n.name for n in decl.names] == ["K", "A"]


def test_var_jump():
    decl = parse("var(jump) C, lam;").statements[0]
    assert isinstance(decl, VarDecl)
    assert decl.kind is VarKind.JUMP
    assert [n.name for n in decl.names] == ["C", "lam"]


def test_var_single_name():
    decl = parse("var Y;").statements[0]
    assert [n.name for n in decl.names] == ["Y"]


# --- valid: varexo declarations -------------------------------------------


def test_varexo_decl():
    decl = parse("varexo A, delta;").statements[0]
    assert isinstance(decl, VarexoDecl)
    assert [n.name for n in decl.names] == ["A", "delta"]


# --- valid: parameters declarations ---------------------------------------


def test_parameters_decl():
    decl = parse("parameters alpha, beta, rho;").statements[0]
    assert isinstance(decl, ParameterDecl)
    assert [n.name for n in decl.names] == ["alpha", "beta", "rho"]


# --- valid: parameter-value assignments -----------------------------------


def test_param_value_int():
    pv = parse("alpha = 1;").statements[0]
    assert isinstance(pv, ParameterValue)
    assert pv.name.name == "alpha"
    assert pv.value.value == 1.0


def test_param_value_float():
    pv = parse("alpha = 0.33;").statements[0]
    assert pv.value.value == pytest.approx(0.33)


def test_param_value_scientific():
    pv = parse("epsilon = 1.5e-6;").statements[0]
    assert pv.value.value == pytest.approx(1.5e-6)


# --- valid: a complete declaration block ---------------------------------


def test_full_declaration_block():
    text = """
    var(state) K, A;
    var(jump)  C;
    var Y, r;
    varexo delta;
    parameters alpha, rho, sigma;
    alpha = 0.33;
    rho   = 0.04;
    sigma = 1.0;
    """
    model = parse(text)
    assert len(model.statements) == 8

    kinds = [type(s).__name__ for s in model.statements]
    assert kinds == [
        "VarDecl",
        "VarDecl",
        "VarDecl",
        "VarexoDecl",
        "ParameterDecl",
        "ParameterValue",
        "ParameterValue",
        "ParameterValue",
    ]


# --- valid: comments are ignored ------------------------------------------


def test_line_comments():
    text = """
    // top of file
    var Y;       // algebraic
    parameters alpha;
    alpha = 0.33;  // calibration
    """
    model = parse(text)
    assert len(model.statements) == 3


def test_block_comments():
    text = """
    /* a block comment
       spanning lines */
    var Y;
    /* inline */ parameters alpha;
    alpha = 0.33;
    """
    model = parse(text)
    assert len(model.statements) == 3


# --- valid: source positions are tracked ----------------------------------


def test_source_positions_tracked():
    text = "var K;\nvarexo A;"
    model = parse(text)
    assert model.statements[0].names[0].pos.line == 1
    assert model.statements[1].names[0].pos.line == 2


# --- invalid: parser/transformer errors -----------------------------------


def test_missing_semicolon_raises():
    with pytest.raises(LarkError):
        parse("var K")


def test_unknown_qualifier_raises():
    # Lexically valid (matches IDENT) but rejected by the transformer.
    with pytest.raises(SyntaxError, match="unknown var qualifier"):
        parse("var(staet) K;")


def test_empty_decl_list_raises():
    with pytest.raises(LarkError):
        parse("var ;")


def test_garbage_input_raises():
    with pytest.raises(LarkError):
        parse("@@@ what is this @@@;")

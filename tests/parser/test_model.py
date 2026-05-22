"""Tests for parsing the model block, equation tags, dict and string literals,
keyword arguments in function calls."""

from __future__ import annotations

import pytest

from continuo.parser import parse
from continuo.parser.ast import (
    BinaryOp,
    DictEntry,
    DictLiteral,
    Equation,
    FunctionCall,
    Identifier,
    KeywordArg,
    ModelBlock,
    NumberLit,
    ParameterValue,
    StringLit,
    UnaryOp,
)
from continuo.parser.errors import LarkError


def _model(text: str) -> ModelBlock:
    """Parse a single ``model; ... end;`` and return the ModelBlock."""
    stmt = parse(text).statements[0]
    assert isinstance(stmt, ModelBlock)
    return stmt


def _rhs(text: str):
    """Parse ``x = <expr>;`` and return the RHS AST node."""
    stmt = parse(f"x = {text};").statements[0]
    assert isinstance(stmt, ParameterValue)
    return stmt.value


# --- model block: structure ----------------------------------------------


def test_empty_model_block():
    mb = _model("model; end;")
    assert mb.equations == []


def test_single_explicit_equation():
    mb = _model("model; Y = A * K^alpha; end;")
    assert len(mb.equations) == 1
    eq = mb.equations[0]
    assert isinstance(eq, Equation)
    assert isinstance(eq.lhs, Identifier) and eq.lhs.name == "Y"
    assert isinstance(eq.rhs, BinaryOp) and eq.rhs.op == "*"
    assert eq.tags == {}


def test_single_bare_expression_equation():
    mb = _model("model; diff(K) - I + delta * K; end;")
    eq = mb.equations[0]
    assert eq.lhs is None  # bare-expression form
    assert isinstance(eq.rhs, BinaryOp)


def test_multiple_equations():
    text = """
    model;
      Y = A * K^alpha;
      r = alpha * Y / K - delta;
      diff(K) = Y - C - delta * K;
      diff(C) = (r - rho) * C / sigma;
    end;
    """
    mb = _model(text)
    assert len(mb.equations) == 4
    # All four are explicit (LHS = RHS) form.
    assert all(eq.lhs is not None for eq in mb.equations)


def test_mixed_equation_forms():
    text = """
    model;
      Y = A * K^alpha;
      diff(K) - I + delta * K;
      r = alpha * Y / K - delta;
    end;
    """
    mb = _model(text)
    assert len(mb.equations) == 3
    assert mb.equations[0].lhs is not None
    assert mb.equations[1].lhs is None  # bare-expression form
    assert mb.equations[2].lhs is not None


# --- equation tags --------------------------------------------------------


def test_equation_with_one_tag():
    text = """
    model;
      [name='euler']
      diff(C) = (r - rho) * C / sigma;
    end;
    """
    mb = _model(text)
    eq = mb.equations[0]
    assert eq.tags == {"name": "euler"}


def test_equation_with_multiple_tags():
    text = """
    model;
      [name='resource', latex='Y = C + I']
      Y = C + I;
    end;
    """
    mb = _model(text)
    eq = mb.equations[0]
    assert eq.tags == {"name": "resource", "latex": "Y = C + I"}


def test_double_quoted_tag_value():
    text = """
    model;
      [name="euler"]
      diff(C) = (r - rho) * C;
    end;
    """
    mb = _model(text)
    assert mb.equations[0].tags == {"name": "euler"}


def test_tag_with_bare_expression_equation():
    text = """
    model;
      [name='resource']
      Y - C - I;
    end;
    """
    mb = _model(text)
    eq = mb.equations[0]
    assert eq.lhs is None
    assert eq.tags == {"name": "resource"}


def test_only_some_equations_tagged():
    text = """
    model;
      Y = A * K^alpha;
      [name='euler']
      diff(C) = (r - rho) * C / sigma;
      r = alpha * Y / K;
    end;
    """
    mb = _model(text)
    assert mb.equations[0].tags == {}
    assert mb.equations[1].tags == {"name": "euler"}
    assert mb.equations[2].tags == {}


# --- string literals as expressions ---------------------------------------


def test_string_literal_single_quoted():
    e = _rhs("'hello'")
    assert isinstance(e, StringLit)
    assert e.value == "hello"


def test_string_literal_double_quoted():
    e = _rhs('"hello"')
    assert isinstance(e, StringLit)
    assert e.value == "hello"


def test_empty_string_literal():
    e = _rhs("''")
    assert isinstance(e, StringLit)
    assert e.value == ""


# --- dict literals --------------------------------------------------------


def test_dict_empty():
    e = _rhs("{}")
    assert isinstance(e, DictLiteral)
    assert e.entries == []


def test_dict_single_entry():
    e = _rhs("{delta: 0.05}")
    assert isinstance(e, DictLiteral)
    assert len(e.entries) == 1
    entry = e.entries[0]
    assert isinstance(entry, DictEntry)
    assert entry.key.name == "delta"
    assert isinstance(entry.value, NumberLit)
    assert entry.value.value == pytest.approx(0.05)


def test_dict_multiple_entries():
    e = _rhs("{delta: 0.05, alpha: 0.33, name: 'baseline'}")
    assert isinstance(e, DictLiteral)
    assert len(e.entries) == 3
    keys = [entry.key.name for entry in e.entries]
    assert keys == ["delta", "alpha", "name"]
    assert isinstance(e.entries[2].value, StringLit)


def test_dict_with_expression_values():
    e = _rhs("{r: rho + 0.01, k: alpha * Y}")
    assert isinstance(e, DictLiteral)
    assert isinstance(e.entries[0].value, BinaryOp)
    assert isinstance(e.entries[1].value, BinaryOp)


# --- keyword arguments in function calls ----------------------------------


def test_function_call_with_kwarg_only():
    e = _rhs("steady_state(K, t=0)")
    assert isinstance(e, FunctionCall)
    assert e.name.name == "steady_state"
    assert len(e.args) == 1
    assert isinstance(e.args[0], Identifier) and e.args[0].name == "K"
    assert len(e.kwargs) == 1
    kw = e.kwargs[0]
    assert isinstance(kw, KeywordArg)
    assert kw.name.name == "t"
    assert isinstance(kw.value, NumberLit) and kw.value.value == 0.0


def test_function_call_with_dict_kwarg():
    e = _rhs("steady_state(K, e={delta: 0.05})")
    assert len(e.args) == 1
    assert e.args[0].name == "K"
    assert len(e.kwargs) == 1
    assert e.kwargs[0].name.name == "e"
    assert isinstance(e.kwargs[0].value, DictLiteral)


def test_function_call_with_multiple_kwargs():
    e = _rhs("f(a, x=1, y=2)")
    assert len(e.args) == 1
    assert len(e.kwargs) == 2
    assert [kw.name.name for kw in e.kwargs] == ["x", "y"]


def test_function_call_only_positional_unchanged():
    # Must still work after adding kwarg syntax.
    e = _rhs("f(a, b, c)")
    assert len(e.args) == 3
    assert e.kwargs == []


# --- combinations: model block uses everything ----------------------------


def test_taylor_rule_with_steady_state_call():
    text = """
    model;
      r = rho + phi * (pi - steady_state(pi));
    end;
    """
    mb = _model(text)
    eq = mb.equations[0]
    # RHS is rho + phi * (pi - steady_state(pi))
    assert isinstance(eq.rhs, BinaryOp) and eq.rhs.op == "+"
    # Drill down to the steady_state call inside the parenthesised diff.
    inner = eq.rhs.right.right  # phi * (pi - steady_state(pi)) -> right side
    # phi * (...)  → mul with left=phi, right=BinaryOp(pi - steady_state(pi))
    assert isinstance(inner, BinaryOp) and inner.op == "-"
    assert isinstance(inner.right, FunctionCall)
    assert inner.right.name.name == "steady_state"


def test_taylor_rule_with_e_override():
    text = """
    model;
      r = rho + phi * (pi - steady_state(pi, e={delta: 0.05}));
    end;
    """
    mb = _model(text)
    eq = mb.equations[0]
    # The steady_state call should have one positional and one kwarg.
    sscall = eq.rhs.right.right.right
    assert isinstance(sscall, FunctionCall)
    assert sscall.name.name == "steady_state"
    assert len(sscall.args) == 1
    assert len(sscall.kwargs) == 1
    assert sscall.kwargs[0].name.name == "e"
    assert isinstance(sscall.kwargs[0].value, DictLiteral)


def test_full_ramsey_model_parses():
    """Ramsey/RBC model from the design's worked-example gallery."""
    text = """
    var(state) K;
    var(jump)  C;
    var Y, r;

    varexo A, delta;

    parameters alpha, rho, sigma;
    alpha = 0.33;
    rho   = 0.04;
    sigma = 1.00;

    model;
      [name='production']
      Y = A * K^alpha;

      [name='real-rate']
      r = alpha * Y / K - delta;

      [name='capital']
      diff(K) = Y - C - delta * K;

      [name='euler']
      diff(C) = (r - rho) * C / sigma;
    end;
    """
    model = parse(text)
    # 3 var decls + 1 varexo + 1 parameters + 3 param values + 1 model block.
    assert len(model.statements) == 9
    mb = model.statements[-1]
    assert isinstance(mb, ModelBlock)
    assert len(mb.equations) == 4
    assert [eq.tags["name"] for eq in mb.equations] == [
        "production",
        "real-rate",
        "capital",
        "euler",
    ]


def test_if_in_model_block_is_just_a_function_call():
    text = """
    model;
      r = rho + phi * if(t < 5, baseline, baseline_new);
    end;
    """
    mb = _model(text)
    eq = mb.equations[0]
    # RHS is rho + phi * if(...)
    if_call = eq.rhs.right.right  # the if() call
    assert isinstance(if_call, FunctionCall)
    assert if_call.name.name == "if"
    assert len(if_call.args) == 3


def test_nested_diff_in_equation():
    # Higher-order derivatives parse as nested function calls;
    # the rewrite to first-order via aux variables happens in IR.
    text = """
    model;
      diff(diff(x)) = a * x;
    end;
    """
    mb = _model(text)
    eq = mb.equations[0]
    assert isinstance(eq.lhs, FunctionCall)
    assert eq.lhs.name.name == "diff"
    inner = eq.lhs.args[0]
    assert isinstance(inner, FunctionCall)
    assert inner.name.name == "diff"


def test_unary_minus_inside_equation():
    text = """
    model;
      diff(C) = -(r - rho) * C;
    end;
    """
    mb = _model(text)
    rhs = mb.equations[0].rhs
    assert isinstance(rhs, BinaryOp) and rhs.op == "*"
    assert isinstance(rhs.left, UnaryOp) and rhs.left.op == "-"


# --- error cases ----------------------------------------------------------


def test_model_missing_end_raises():
    with pytest.raises(LarkError):
        parse("model; Y = K^alpha;")


def test_model_missing_semicolon_after_end_raises():
    with pytest.raises(LarkError):
        parse("model; Y = K^alpha; end")


def test_equation_missing_semicolon_raises():
    with pytest.raises(LarkError):
        parse("model; Y = K^alpha end;")


def test_unclosed_dict_raises():
    with pytest.raises(LarkError):
        parse("x = {a: 1, b: 2;")


def test_unclosed_string_raises():
    with pytest.raises(LarkError):
        parse("x = 'hello;")


def test_unclosed_tag_brackets_raises():
    with pytest.raises(LarkError):
        parse("model; [name='foo' Y = 1; end;")


def test_kwarg_without_value_raises():
    with pytest.raises(LarkError):
        parse("x = f(a, b=);")

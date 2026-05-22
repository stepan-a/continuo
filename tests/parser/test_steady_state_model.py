"""Tests for parsing the steady_state_model block."""

from __future__ import annotations

import pytest

from continuo.parser import parse
from continuo.parser.ast import (
    Assignment,
    BinaryOp,
    FunctionCall,
    Identifier,
    InitvalBlock,
    ModelBlock,
    NumberLit,
    ShocksBlock,
    SteadyStateModelBlock,
    UnaryOp,
)
from continuo.parser.errors import LarkError


def _ssm(text: str) -> SteadyStateModelBlock:
    """Parse a single steady_state_model block; return the block."""
    stmt = parse(text).statements[0]
    assert isinstance(stmt, SteadyStateModelBlock)
    return stmt


# --- structure -----------------------------------------------------------


def test_empty_steady_state_model():
    ssm = _ssm("steady_state_model; end;")
    assert ssm.assignments == []


def test_single_assignment():
    ssm = _ssm("steady_state_model; r = rho; end;")
    assert len(ssm.assignments) == 1
    a = ssm.assignments[0]
    assert isinstance(a, Assignment)
    assert isinstance(a.lhs, Identifier) and a.lhs.name == "r"
    assert isinstance(a.rhs, Identifier) and a.rhs.name == "rho"


def test_multiple_assignments_with_dependencies():
    """Top-down evaluation order: each assignment may depend on prior ones."""
    ssm = _ssm(
        """
        steady_state_model;
          K = ((alpha * A) / (rho + delta))^(1/(1-alpha));
          Y = A * K^alpha;
          C = Y - delta * K;
          r = rho;
        end;
        """
    )
    names = [a.lhs.name for a in ssm.assignments]
    assert names == ["K", "Y", "C", "r"]


def test_rhs_uses_parameters_and_varexos():
    """Parameters and varexos appear on the RHS — that's how /e/ enters /h/."""
    ssm = _ssm(
        """
        steady_state_model;
          K = ((alpha * A) / (rho + delta))^(1/(1-alpha));
        end;
        """
    )
    rhs = ssm.assignments[0].rhs
    # RHS is ((alpha * A) / (rho + delta))^(1/(1-alpha)).
    assert isinstance(rhs, BinaryOp) and rhs.op == "^"


def test_rhs_with_function_call():
    ssm = _ssm("steady_state_model; K = exp(log_K_ss); end;")
    rhs = ssm.assignments[0].rhs
    assert isinstance(rhs, FunctionCall)
    assert rhs.name.name == "exp"


def test_negative_value_on_rhs():
    ssm = _ssm("steady_state_model; w = -rho; end;")
    rhs = ssm.assignments[0].rhs
    assert isinstance(rhs, UnaryOp) and rhs.op == "-"


def test_numeric_constant_on_rhs():
    ssm = _ssm("steady_state_model; A = 1.0; end;")
    rhs = ssm.assignments[0].rhs
    assert isinstance(rhs, NumberLit)
    assert rhs.value == 1.0


# --- LHS shape (parser-level lenience; IR enforces "endogenous only") ----


def test_lhs_can_syntactically_be_anything():
    """The grammar accepts any expr on the LHS; the IR enforces that
    the LHS is a declared endogenous variable. This test is a reminder
    that the parser does not catch this — the IR layer does."""
    # Syntactically valid (but semantically wrong) — should parse fine.
    parse("steady_state_model; alpha = 0.33; end;")
    parse("steady_state_model; A = 1.0; end;")  # 'A' might be a varexo
    # Both parse; the IR will reject when it knows the declarations.


# --- gallery integration -------------------------------------------------


def test_full_unanticipated_permanent_change_example():
    """Example 2 from the design's worked-examples gallery — now parses
    end-to-end except for the simulate command (step 7)."""
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
      Y = A * K^alpha;
      r = alpha * Y / K - delta;
      diff(K) = Y - C - delta * K;
      diff(C) = (r - rho) * C / sigma;
    end;

    steady_state_model;
      K = ((alpha * A) / (rho + delta))^(1/(1-alpha));
      Y = A * K^alpha;
      C = Y - delta * K;
      r = rho;
    end;

    shocks;
      var A;
      path = 1.0;

      var delta;
      path at t=0 = 0.05;
      path at t=5 = 0.06;
    end;

    initval(steady);
    end;
    """
    model = parse(text)
    # 3 var decls + 1 varexo + 1 parameters + 3 param values + model
    # + steady_state_model + shocks + initval = 12.
    assert len(model.statements) == 12
    # Locate each block and sanity-check.
    mb = next(s for s in model.statements if isinstance(s, ModelBlock))
    ssm = next(s for s in model.statements if isinstance(s, SteadyStateModelBlock))
    sb = next(s for s in model.statements if isinstance(s, ShocksBlock))
    iv = next(s for s in model.statements if isinstance(s, InitvalBlock))
    assert len(mb.equations) == 4
    assert len(ssm.assignments) == 4
    assert len(sb.entries) == 2
    assert iv.steady is True


def test_full_anticipated_permanent_change_example():
    """Example 1 from the gallery — single-belief path with `if`."""
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
      Y = A * K^alpha;
      r = alpha * Y / K - delta;
      diff(K) = Y - C - delta * K;
      diff(C) = (r - rho) * C / sigma;
    end;

    steady_state_model;
      K = ((alpha * A) / (rho + delta))^(1/(1-alpha));
      Y = A * K^alpha;
      C = Y - delta * K;
      r = rho;
    end;

    shocks;
      var A;     path = 1.0;
      var delta; path = if(t < 5, 0.05, 0.06);
    end;

    initval(steady);
    end;
    """
    model = parse(text)
    sb = next(s for s in model.statements if isinstance(s, ShocksBlock))
    delta_entry = next(e for e in sb.entries if e.name.name == "delta")
    assert len(delta_entry.paths) == 1
    assert delta_entry.paths[0].reveal_time is None  # default form


def test_full_instantaneous_permanent_change_example():
    """Example 6 — requires the `e=` override on initval(steady)."""
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
      Y = A * K^alpha;
      r = alpha * Y / K - delta;
      diff(K) = Y - C - delta * K;
      diff(C) = (r - rho) * C / sigma;
    end;

    steady_state_model;
      K = ((alpha * A) / (rho + delta))^(1/(1-alpha));
      Y = A * K^alpha;
      C = Y - delta * K;
      r = rho;
    end;

    shocks;
      var A;     path = 1.0;
      var delta; path = 0.06;
    end;

    initval(steady, e={delta: 0.05});
    end;
    """
    model = parse(text)
    iv = next(s for s in model.statements if isinstance(s, InitvalBlock))
    assert iv.steady is True
    assert len(iv.kwargs) == 1
    assert iv.kwargs[0].name.name == "e"


# --- error cases ----------------------------------------------------------


def test_missing_end_raises():
    with pytest.raises(LarkError):
        parse("steady_state_model; K = 10;")


def test_missing_semicolon_after_end_raises():
    with pytest.raises(LarkError):
        parse("steady_state_model; K = 10; end")


def test_assignment_missing_semicolon_raises():
    with pytest.raises(LarkError):
        parse("steady_state_model; K = 10 end;")


def test_unbalanced_parens_in_rhs_raises():
    with pytest.raises(LarkError):
        parse("steady_state_model; K = (alpha * A; end;")

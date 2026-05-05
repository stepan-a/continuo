"""Tests for parsing the initval and initial_guess blocks."""

from __future__ import annotations

import pytest

from dynare_ct.parser import parse
from dynare_ct.parser.ast import (
    Assignment,
    BinaryOp,
    DictLiteral,
    FunctionCall,
    Identifier,
    InitialGuessBlock,
    InitvalBlock,
    NumberLit,
)
from dynare_ct.parser.errors import LarkError


def _initval(text: str) -> InitvalBlock:
    """Parse a single initval block; return the InitvalBlock."""
    stmt = parse(text).statements[0]
    assert isinstance(stmt, InitvalBlock)
    return stmt


def _initial_guess(text: str) -> InitialGuessBlock:
    """Parse a single initial_guess block; return the InitialGuessBlock."""
    stmt = parse(text).statements[0]
    assert isinstance(stmt, InitialGuessBlock)
    return stmt


# --- initval: structure ---------------------------------------------------


def test_empty_initval():
    iv = _initval("initval; end;")
    assert iv.steady is False
    assert iv.kwargs == []
    assert iv.assignments == []


def test_initval_one_assignment():
    iv = _initval("initval; K = 10; end;")
    assert iv.steady is False
    assert len(iv.assignments) == 1
    a = iv.assignments[0]
    assert isinstance(a, Assignment)
    assert isinstance(a.lhs, Identifier) and a.lhs.name == "K"
    assert isinstance(a.rhs, NumberLit) and a.rhs.value == 10.0


def test_initval_multiple_assignments():
    iv = _initval(
        """
        initval;
          K = 10;
          A = 1;
          L = 0.6;
        end;
        """
    )
    assert len(iv.assignments) == 3
    names = [a.lhs.name for a in iv.assignments]
    assert names == ["K", "A", "L"]


def test_initval_assignment_with_expression_rhs():
    iv = _initval("initval; K = 0.9 * steady_state(K); end;")
    a = iv.assignments[0]
    assert isinstance(a.rhs, BinaryOp) and a.rhs.op == "*"


def test_initval_assignment_with_diff_lhs():
    # diff(x) on the LHS — parser admits it as a generic FunctionCall;
    # the IR layer interprets it as the auxiliary state's initial value.
    iv = _initval("initval; x = 0; diff(x) = 1; end;")
    assert len(iv.assignments) == 2
    a2 = iv.assignments[1]
    assert isinstance(a2.lhs, FunctionCall)
    assert a2.lhs.name.name == "diff"
    assert len(a2.lhs.args) == 1


def test_initval_assignment_with_higher_order_diff_lhs():
    iv = _initval("initval; diff(x, 2) = 0; end;")
    a = iv.assignments[0]
    assert isinstance(a.lhs, FunctionCall)
    assert a.lhs.name.name == "diff"
    assert len(a.lhs.args) == 2
    assert isinstance(a.lhs.args[1], NumberLit) and a.lhs.args[1].value == 2.0


# --- initval: (steady) qualifier -----------------------------------------


def test_initval_steady_only():
    iv = _initval("initval(steady); end;")
    assert iv.steady is True
    assert iv.kwargs == []
    assert iv.assignments == []


def test_initval_steady_with_overrides():
    iv = _initval(
        """
        initval(steady);
          K = 5;
        end;
        """
    )
    assert iv.steady is True
    assert iv.kwargs == []
    assert len(iv.assignments) == 1
    assert iv.assignments[0].lhs.name == "K"


def test_initval_steady_with_e_kwarg():
    iv = _initval("initval(steady, e={delta: 0.05}); end;")
    assert iv.steady is True
    assert len(iv.kwargs) == 1
    kw = iv.kwargs[0]
    assert kw.name.name == "e"
    assert isinstance(kw.value, DictLiteral)
    assert len(kw.value.entries) == 1
    assert kw.value.entries[0].key.name == "delta"


def test_initval_steady_with_e_and_overrides():
    iv = _initval(
        """
        initval(steady, e={delta: 0.05});
          K = 5;
          A = 1.1;
        end;
        """
    )
    assert iv.steady is True
    assert len(iv.kwargs) == 1
    assert iv.kwargs[0].name.name == "e"
    assert len(iv.assignments) == 2


def test_initval_steady_with_multiple_kwargs():
    # The grammar allows any number of kwargs after "steady",
    # not just `e=...`. Future-proof for additional options.
    iv = _initval("initval(steady, e={delta: 0.05}, t=0); end;")
    assert iv.steady is True
    assert len(iv.kwargs) == 2
    names = [kw.name.name for kw in iv.kwargs]
    assert names == ["e", "t"]


# --- initial_guess --------------------------------------------------------


def test_empty_initial_guess():
    ig = _initial_guess("initial_guess; end;")
    assert ig.assignments == []


def test_initial_guess_assignments():
    ig = _initial_guess(
        """
        initial_guess;
          C = 0.8;
          L = 0.6;
        end;
        """
    )
    assert len(ig.assignments) == 2
    names = [a.lhs.name for a in ig.assignments]
    assert names == ["C", "L"]


def test_initial_guess_with_expression_rhs():
    ig = _initial_guess("initial_guess; K = steady_state(K); end;")
    a = ig.assignments[0]
    assert isinstance(a.rhs, FunctionCall)
    assert a.rhs.name.name == "steady_state"


# --- combinations: full file ---------------------------------------------


def test_full_file_with_initval():
    text = """
    var(state) K;
    var(jump)  C;
    var Y, r;

    varexo A, delta;

    parameters alpha, rho;
    alpha = 0.33;
    rho   = 0.04;

    model;
      Y = A * K^alpha;
      diff(K) = Y - C - delta * K;
    end;

    initval(steady, e={delta: 0.05});
      K = 5;
    end;

    initial_guess;
      C = 0.8;
    end;
    """
    model = parse(text)
    # Locate the new blocks.
    iv = next(s for s in model.statements if isinstance(s, InitvalBlock))
    ig = next(s for s in model.statements if isinstance(s, InitialGuessBlock))
    assert iv.steady is True
    assert iv.kwargs[0].name.name == "e"
    assert len(iv.assignments) == 1 and iv.assignments[0].lhs.name == "K"
    assert len(ig.assignments) == 1 and ig.assignments[0].lhs.name == "C"


# --- error cases ----------------------------------------------------------


def test_initval_missing_end_raises():
    with pytest.raises(LarkError):
        parse("initval; K = 10;")


def test_initval_missing_semicolon_after_end_raises():
    with pytest.raises(LarkError):
        parse("initval; K = 10; end")


def test_initval_assignment_missing_semicolon_raises():
    with pytest.raises(LarkError):
        parse("initval; K = 10 end;")


def test_initval_unknown_qualifier_raises():
    # Anything but "steady" inside the qualifier is rejected at parse time.
    with pytest.raises(LarkError):
        parse("initval(notreallyaqualifier); end;")


def test_initial_guess_missing_end_raises():
    with pytest.raises(LarkError):
        parse("initial_guess; C = 0.8;")

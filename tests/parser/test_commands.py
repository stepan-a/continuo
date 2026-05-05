"""Tests for the simulate and steady commands.

After this step the parser is feature-complete: the six worked-example
files from the design's gallery parse end-to-end. A handful of those
end-to-end tests live here as a celebratory check.
"""

from __future__ import annotations

import pytest

from dynare_ct.parser import parse
from dynare_ct.parser.ast import (
    DictLiteral,
    Identifier,
    NumberLit,
    SimulateCommand,
    SteadyCommand,
)
from dynare_ct.parser.errors import LarkError


def _last(text: str):
    return parse(text).statements[-1]


# --- simulate ------------------------------------------------------------


def test_simulate_with_T_and_N():
    cmd = _last("simulate(T=200, N=400);")
    assert isinstance(cmd, SimulateCommand)
    assert cmd.args == []
    assert len(cmd.kwargs) == 2
    assert [kw.name.name for kw in cmd.kwargs] == ["T", "N"]
    assert isinstance(cmd.kwargs[0].value, NumberLit) and cmd.kwargs[0].value.value == 200.0
    assert cmd.kwargs[1].value.value == 400.0


def test_simulate_with_scheme_kwarg():
    cmd = _last("simulate(T=200, N=400, scheme=radau);")
    assert isinstance(cmd, SimulateCommand)
    assert len(cmd.kwargs) == 3
    scheme = cmd.kwargs[2]
    assert scheme.name.name == "scheme"
    assert isinstance(scheme.value, Identifier) and scheme.value.name == "radau"


def test_simulate_with_extra_kwargs_parses():
    """The grammar accepts any kwargs; the IR validates the supported set."""
    cmd = _last("simulate(T=200, N=400, tol=1e-9, maxiter=50);")
    assert isinstance(cmd, SimulateCommand)
    assert [kw.name.name for kw in cmd.kwargs] == ["T", "N", "tol", "maxiter"]


def test_simulate_real_T():
    cmd = _last("simulate(T=200.0, N=400);")
    assert cmd.kwargs[0].value.value == pytest.approx(200.0)


# --- steady --------------------------------------------------------------


def test_steady_bare():
    cmd = _last("steady;")
    assert isinstance(cmd, SteadyCommand)
    assert cmd.args == []
    assert cmd.kwargs == []


def test_steady_at_t0():
    cmd = _last("steady(t=0);")
    assert isinstance(cmd, SteadyCommand)
    assert len(cmd.kwargs) == 1
    assert cmd.kwargs[0].name.name == "t"
    assert cmd.kwargs[0].value.value == 0.0


def test_steady_at_intermediate_time():
    cmd = _last("steady(t=5);")
    assert cmd.kwargs[0].value.value == 5.0


def test_steady_with_e_override():
    cmd = _last("steady(t=0, e={delta: 0.05});")
    assert isinstance(cmd, SteadyCommand)
    assert len(cmd.kwargs) == 2
    assert cmd.kwargs[1].name.name == "e"
    assert isinstance(cmd.kwargs[1].value, DictLiteral)


# --- gallery integration: all six examples parse end-to-end --------------


_BASE_HEADER = """
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
"""


def test_gallery_example_1_anticipated_permanent():
    text = (
        _BASE_HEADER
        + """
    shocks;
      var A;     path = 1.0;
      var delta; path = if(t < 5, 0.05, 0.06);
    end;

    initval(steady);
    end;

    simulate(T=200, N=400);
    """
    )
    model = parse(text)
    assert isinstance(model.statements[-1], SimulateCommand)


def test_gallery_example_2_unanticipated_permanent():
    text = (
        _BASE_HEADER
        + """
    shocks;
      var A;     path = 1.0;
      var delta;
      path at t=0 = 0.05;
      path at t=5 = 0.06;
    end;

    initval(steady);
    end;

    simulate(T=200, N=400);
    """
    )
    model = parse(text)
    assert isinstance(model.statements[-1], SimulateCommand)


def test_gallery_example_3_anticipated_transitory():
    text = (
        _BASE_HEADER
        + """
    shocks;
      var delta; path = 0.05;
      var A;     path = 1.0 + 0.05 * pulse(t, 8, 12);
    end;

    initval(steady);
    end;

    simulate(T=200, N=400);
    """
    )
    parse(text)


def test_gallery_example_4_unanticipated_transitory():
    text = (
        _BASE_HEADER
        + """
    shocks;
      var delta; path = 0.05;
      var A;
      path at t=0 = 1.0;
      path at t=5 = 1.0 + 0.05 * expdecay(t, 5, 3);
    end;

    initval(steady);
    end;

    simulate(T=200, N=400);
    """
    )
    parse(text)


def test_gallery_example_5_sequential_surprises():
    text = (
        _BASE_HEADER
        + """
    shocks;
      var delta; path = 0.05;
      var A;
      path at t=0  = 1.0;
      path at t=5  = 1.05;
      path at t=10 = 0.97;
    end;

    initval(steady);
    end;

    simulate(T=200, N=400);
    """
    )
    model = parse(text)
    # Three reveal times → three path assignments on A.
    from dynare_ct.parser.ast import ShocksBlock

    sb = next(s for s in model.statements if isinstance(s, ShocksBlock))
    a_entry = next(e for e in sb.entries if e.name.name == "A")
    assert len(a_entry.paths) == 3


def test_gallery_example_6_instantaneous_permanent():
    text = (
        _BASE_HEADER
        + """
    shocks;
      var A;     path = 1.0;
      var delta; path = 0.06;
    end;

    initval(steady, e={delta: 0.05});
    end;

    simulate(T=200, N=400);
    """
    )
    model = parse(text)
    from dynare_ct.parser.ast import InitvalBlock

    iv = next(s for s in model.statements if isinstance(s, InitvalBlock))
    assert iv.steady is True
    assert iv.kwargs[0].name.name == "e"


# --- error cases ---------------------------------------------------------


def test_simulate_missing_args_raises():
    # The grammar requires arg_list (non-empty) inside the parens.
    with pytest.raises(LarkError):
        parse("simulate();")


def test_simulate_missing_parens_raises():
    with pytest.raises(LarkError):
        parse("simulate;")


def test_simulate_missing_semicolon_raises():
    with pytest.raises(LarkError):
        parse("simulate(T=200, N=400)")


def test_steady_missing_semicolon_raises():
    with pytest.raises(LarkError):
        parse("steady")


def test_steady_unbalanced_paren_raises():
    with pytest.raises(LarkError):
        parse("steady(t=0;")

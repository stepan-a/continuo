"""Tests for the top-level programmatic API."""

from __future__ import annotations

import pytest

import dynare_ct
from dynare_ct import Model, Solution

RBC = """
var(state) K, A;
var(jump) C;
var Y;
varexo z;
parameters alpha, delta, rho;
alpha = 0.33;
delta = 0.1;
rho = 0.05;
model;
  diff(K) = Y - C - delta * K;
  diff(A) = z - A;
  diff(C) = C * (alpha * Y / K - delta - rho);
  Y = A * K^alpha;
end;
steady_state_model;
  A = z;
  K = (alpha * z / (rho + delta))^(1 / (1 - alpha));
  Y = z * K^alpha;
  C = Y - delta * K;
end;
initval(steady);
end;
shocks;
  var z;
  path = 1;
end;
simulate(T=40, N=200);
"""

SADDLE = """
var(state) x;
var(jump) y;
model;
  diff(x) = -x;
  diff(y) = y;
end;
initval;
  x = 1;
end;
simulate(T=5, N=20);
"""


def test_parse_string_returns_a_model():
    model = dynare_ct.parse_string(SADDLE)
    assert isinstance(model, Model)
    assert model.states == ("x",)
    assert model.jumps == ("y",)


def test_model_inspection_properties():
    model = dynare_ct.parse_string(RBC)
    assert model.states == ("K", "A")
    assert model.jumps == ("C",)
    assert model.algebraic == ("Y",)
    assert model.exogenous == ("z",)
    assert set(model.parameters) == {"alpha", "delta", "rho"}
    assert "Model" in repr(model)


def test_simul_returns_a_solution():
    sol = dynare_ct.parse_string(SADDLE).simul()
    assert isinstance(sol, Solution)
    assert sol.t.shape == (21,)
    assert sol["x"][0] == pytest.approx(1.0)


def test_simul_reads_the_command_and_overrides():
    model = dynare_ct.parse_string(SADDLE)
    assert model.simul().t[-1] == pytest.approx(5.0)
    assert model.simul(horizon=2.0, intervals=4).t[-1] == pytest.approx(2.0)


def test_steady_state():
    ss = dynare_ct.parse_string(RBC).steady_state(exogenous={"z": 1.0})
    # K* = (alpha z / (rho + delta))^(1/(1-alpha))
    expected_k = (0.33 * 1.0 / (0.05 + 0.1)) ** (1 / (1 - 0.33))
    assert ss["K"] == pytest.approx(expected_k, rel=1e-6)


def test_end_to_end_rbc_transition():
    # Start with capital 10% below its steady state and check it climbs back.
    src = RBC.replace(
        "initval(steady);\nend;",
        "initval;\n  K = 0.9 * steady_state(K);\n  A = steady_state(A);\nend;",
    )
    sol = dynare_ct.parse_string(src).simul()
    ss = dynare_ct.parse_string(RBC).steady_state(exogenous={"z": 1.0})
    assert sol["K"][0] == pytest.approx(0.9 * ss["K"], rel=1e-6)
    assert sol["K"][-1] == pytest.approx(ss["K"], rel=1e-3)  # returns to SS


def test_parse_reads_a_file(tmp_path):
    path = tmp_path / "saddle.mod"
    path.write_text(SADDLE)
    model = dynare_ct.parse(path)
    assert model.simul().t[-1] == pytest.approx(5.0)


def test_parse_resolves_includes(tmp_path):
    (tmp_path / "params.mod").write_text("parameters a;\na = 2;\n")
    main = tmp_path / "main.mod"
    main.write_text(
        '@#include "params.mod"\n'
        "var(state) x;\nvar(jump) y;\n"
        "model;\n  diff(x) = a - x;\n  diff(y) = y;\nend;\n"
        "initval;\n  x = 0;\nend;\n"
        "simulate(T=20, N=200);"
    )
    sol = dynare_ct.parse(main).simul()
    assert sol["x"][-1] == pytest.approx(2.0, abs=1e-3)  # x* = a = 2

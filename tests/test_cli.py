"""Tests for the command-line interface."""

from __future__ import annotations

import csv

import pytest

from continuo.cli import _parse_options, main
from continuo.solve import SolveError

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


def write_model(tmp_path, source=SADDLE, name="model.mod"):
    path = tmp_path / name
    path.write_text(source)
    return path


def read_csv(path):
    with open(path, newline="") as handle:
        return list(csv.reader(handle))


def test_writes_csv_next_to_the_model(tmp_path, capsys):
    model = write_model(tmp_path)
    assert main([str(model)]) == 0
    output = tmp_path / "model.csv"
    assert output.exists()
    rows = read_csv(output)
    assert rows[0] == ["t", "x", "y"]
    assert len(rows) == 22  # header + 21 grid points
    assert "wrote 21 rows" in capsys.readouterr().out


def test_explicit_output_path(tmp_path):
    model = write_model(tmp_path)
    out = tmp_path / "result.csv"
    assert main([str(model), "-o", str(out)]) == 0
    assert out.exists()


def test_horizon_and_grid_overrides(tmp_path):
    model = write_model(tmp_path)
    assert main([str(model), "-T", "2", "-N", "4"]) == 0
    rows = read_csv(tmp_path / "model.csv")
    assert len(rows) == 6  # header + 5 grid points
    assert float(rows[-1][0]) == pytest.approx(2.0)


def test_solver_flag_selects_a_backend(tmp_path):
    model = write_model(tmp_path)
    assert main([str(model), "--solver", "superlu"]) == 0
    assert (tmp_path / "model.csv").exists()


def test_unknown_solver_flag_reports_error(tmp_path, capsys):
    # A bogus --solver only errors if the flag is actually threaded through.
    model = write_model(tmp_path)
    assert main([str(model), "--solver", "bogus"]) == 1
    assert "bogus" in capsys.readouterr().err


def test_steady_solver_and_option_flags(tmp_path):
    model = write_model(tmp_path)
    rc = main(
        [str(model), "--steady-solver", "newton", "--steady-solver-option", "line_search_steps=10"]
    )
    assert rc == 0
    assert (tmp_path / "model.csv").exists()


def test_steady_solver_option_without_solver_errors(tmp_path, capsys):
    # Options need a named solver: 'auto' (the default) rejects them.
    model = write_model(tmp_path)
    assert main([str(model), "--steady-solver-option", "strategy=picard"]) == 1
    assert "auto" in capsys.readouterr().err


def test_parse_options_coerces_values():
    assert _parse_options(["strategy=picard", "steps=20", "factor=0.1"]) == {
        "strategy": "picard",
        "steps": 20,
        "factor": 0.1,
    }


def test_parse_options_empty_is_none():
    assert _parse_options(None) is None
    assert _parse_options([]) is None


def test_parse_options_rejects_malformed():
    with pytest.raises(SolveError, match="KEY=VALUE"):
        _parse_options(["nope"])


def test_missing_file_reports_error(tmp_path, capsys):
    assert main([str(tmp_path / "nope.mod")]) == 1
    assert "cannot read" in capsys.readouterr().err


def test_model_error_is_reported_cleanly(tmp_path, capsys):
    # A state with no time derivative is an IR error.
    bad = write_model(tmp_path, "var(state) K;\nvar Y;\nmodel;\n  K = Y;\n  Y = 1;\nend;")
    assert main([str(bad)]) == 1
    err = capsys.readouterr().err
    assert err.startswith("continuo: error:")
    assert "K" in err


def test_no_simulate_command_reports_error(tmp_path, capsys):
    src = """
    var(state) x;
    var(jump) y;
    model;
      diff(x) = -x;
      diff(y) = y;
    end;
    initval;
      x = 1;
    end;
    """
    bad = write_model(tmp_path, src)
    assert main([str(bad)]) == 1
    assert "no simulate command" in capsys.readouterr().err

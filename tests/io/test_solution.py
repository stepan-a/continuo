"""Tests for the Solution object and its conversions."""

from __future__ import annotations

import builtins
import sys

import numpy as np
import pytest

from continuo.io import Segment, Solution
from continuo.ir import build
from continuo.parser import parse
from continuo.solve import simulate

TRACKER = """
var(state) x;
var(jump) y;
varexo u;
model;
  diff(x) = u - x;
  diff(y) = y;
end;
initval;
  x = 0;
end;
"""

SURPRISE = (
    TRACKER + "shocks;\n  var u;\n  path = 0.5;\n  path at t=5 = 1;\nend;\nsimulate(T=20, N=200);"
)


def model(src: str):
    return build(parse(src))


# --- access ---------------------------------------------------------------


def test_indexing_and_attribute_access_agree():
    sol = simulate(model(TRACKER + "simulate(T=2, N=4);"))
    np.testing.assert_array_equal(sol["x"], sol.x)
    assert sol["x"].shape == sol.t.shape


def test_unknown_variable_attribute_raises():
    sol = simulate(model(TRACKER + "simulate(T=2, N=4);"))
    with pytest.raises(AttributeError):
        _ = sol.nonexistent


def test_full_grid_and_path_shapes():
    sol = simulate(model(TRACKER + "simulate(T=10, N=50);"))
    assert sol.t.shape == (51,)
    assert sol.path.shape == (51, 2)
    assert sol.t[0] == 0.0 and sol.t[-1] == pytest.approx(10.0)


# --- segments and metadata ------------------------------------------------


def test_single_segment_without_surprises():
    sol = simulate(model(TRACKER + "shocks;\n var u;\n path = 1;\nend;\nsimulate(T=10, N=50);"))
    assert len(sol.segments) == 1
    assert sol.segments[0].info_set["u"] == pytest.approx(1.0)


def test_segments_carry_revelation_metadata():
    sol = simulate(model(SURPRISE))
    assert len(sol.segments) == 2
    first, second = sol.segments
    assert first.start_time == pytest.approx(0.0)
    assert second.start_time == pytest.approx(5.0)
    assert first.info_set["u"] == pytest.approx(0.5)  # old belief
    assert second.info_set["u"] == pytest.approx(1.0)  # belief after the surprise
    assert second.terminal_ss["x"] == pytest.approx(1.0)  # new SS anchor


def test_segments_glue_into_the_full_grid_without_duplicates():
    sol = simulate(model(SURPRISE))
    glued = np.concatenate([seg.times for seg in sol.segments])
    np.testing.assert_array_equal(sol.t, glued)
    assert len(np.unique(sol.t)) == len(sol.t)  # each reveal time once


def test_diagnostics():
    sol = simulate(model(SURPRISE))
    assert sol.diagnostics["segments"] == 2
    assert sol.diagnostics["scheme"] == "crank_nicolson"
    assert sol.diagnostics["newton_iterations"] >= 1
    assert sol.converged is True


# --- conversions (optional dependencies) ----------------------------------


def test_to_dataframe():
    pd = pytest.importorskip("pandas")
    sol = simulate(model(TRACKER + "simulate(T=2, N=4);"))
    frame = sol.to_dataframe()
    assert list(frame.columns) == ["x", "y"]
    assert frame.index.name == "t"
    assert len(frame) == 5
    np.testing.assert_array_equal(frame["x"].to_numpy(), sol["x"])
    assert isinstance(frame, pd.DataFrame)


def test_to_xarray():
    pytest.importorskip("xarray")
    sol = simulate(model(TRACKER + "simulate(T=2, N=4);"))
    dataset = sol.to_xarray()
    assert set(dataset.data_vars) == {"x", "y"}
    np.testing.assert_array_equal(dataset["x"].to_numpy(), sol["x"])
    np.testing.assert_array_equal(dataset.coords["t"].to_numpy(), sol.t)


def _hide_module(monkeypatch, name):
    """Make ``import <name>`` raise ImportError until the patch is undone."""
    real_import = builtins.__import__

    def fake_import(modname, *args, **kwargs):
        if modname == name or modname.startswith(name + "."):
            raise ImportError(f"No module named '{name}'")
        return real_import(modname, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.delitem(sys.modules, name, raising=False)


def test_to_dataframe_without_pandas_gives_hint(monkeypatch):
    sol = simulate(model(TRACKER + "simulate(T=2, N=4);"))
    _hide_module(monkeypatch, "pandas")
    with pytest.raises(ImportError, match=r"continuo\[pandas\]"):
        sol.to_dataframe()


def test_to_xarray_without_xarray_gives_hint(monkeypatch):
    sol = simulate(model(TRACKER + "simulate(T=2, N=4);"))
    _hide_module(monkeypatch, "xarray")
    with pytest.raises(ImportError, match=r"continuo\[xarray\]"):
        sol.to_xarray()


# --- direct construction --------------------------------------------------


def test_empty_solution():
    sol = Solution(segments=(), names=("x",))
    assert sol.t.shape == (0,)
    assert sol.path.shape == (0, 1)


def test_segment_indexing():
    seg = Segment(
        start_time=0.0,
        times=np.array([0.0, 1.0]),
        path=np.array([[1.0, 2.0], [3.0, 4.0]]),
        names=("a", "b"),
        info_set={},
        terminal_ss={},
        iterations=0,
    )
    np.testing.assert_array_equal(seg["b"], np.array([2.0, 4.0]))

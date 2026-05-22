"""Tests for C codegen and compilation of the residual.

These require a C compiler; the module is skipped when none is found.
Compilation is done once (module-scoped fixture) and reused.
"""

from __future__ import annotations

import os
import shutil

import casadi as ca
import pytest

from continuo.codegen import CodegenError, build_residual, compile_residual
from continuo.ir import build
from continuo.parser import parse

pytestmark = pytest.mark.skipif(
    shutil.which(os.environ.get("CC", "gcc")) is None, reason="no C compiler available"
)

SRC = """
var(state) K;
var Y;
parameters alpha;
alpha = 0.5;
model;
  diff(K) = Y - K;
  Y = K^alpha;
end;
"""

EMPTY = ca.DM.zeros(0, 1)
# Sample evaluation point: xdot=[dK=1], x=[K=4, Y=2], e=[], theta=[0.5], t=0.
POINT = (ca.DM([1.0]), ca.DM([4.0, 2.0]), EMPTY, ca.DM([0.5]), 0.0)


@pytest.fixture(scope="module")
def built():
    return build_residual(build(parse(SRC)))


@pytest.fixture(scope="module")
def compiled(built):
    return compile_residual(built, name="rbc")


# --- artifacts ------------------------------------------------------------


def test_artifacts_written(compiled):
    assert compiled.source.exists() and compiled.source.suffix == ".c"
    assert compiled.library.exists()


def test_custom_directory(built, tmp_path):
    result = compile_residual(built, name="here", directory=tmp_path)
    assert result.source == tmp_path / "here.c"
    assert result.library.parent == tmp_path
    assert result.library.exists()


# --- compiled results match the interpreted ones --------------------------


def test_compiled_residual_matches(built, compiled):
    interpreted = built.function(*POINT)
    native = compiled.function(*POINT)
    assert float(native[0]) == pytest.approx(float(interpreted[0]))
    assert float(native[1]) == pytest.approx(float(interpreted[1]))


def test_compiled_residual_values(compiled):
    F = compiled.function(*POINT)
    assert float(F[0]) == pytest.approx(3.0)  # 1 - (2 - 4)
    assert float(F[1]) == pytest.approx(0.0)  # 2 - sqrt(4)


def test_compiled_jacobian_x_matches(built, compiled):
    interpreted = built.jacobian_x(*POINT)
    native = compiled.jacobian_x(*POINT)
    assert native.shape == (2, 2)
    for i in range(2):
        for j in range(2):
            assert float(native[i, j]) == pytest.approx(float(interpreted[i, j]))


def test_compiled_jacobian_xdot_matches(built, compiled):
    native = compiled.jacobian_xdot(*POINT)
    assert native.shape == (2, 1)
    assert float(native[0, 0]) == pytest.approx(1.0)
    assert float(native[1, 0]) == pytest.approx(0.0)


# --- error path -----------------------------------------------------------


def test_missing_compiler_errors(built, tmp_path):
    with pytest.raises(CodegenError, match="not found"):
        compile_residual(built, directory=tmp_path, compiler="no_such_compiler_xyz")

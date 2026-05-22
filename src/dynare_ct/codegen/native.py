"""C codegen and compilation of the model residual.

CasADi generates self-contained C for the residual ``F`` and its
Jacobians; we compile that to a shared library with ``-O3`` and load the
functions back through ``ca.external``. This is done once per model, after
which evaluation runs as compiled native code with negligible Python
overhead.

The compiled functions keep the same signatures as the interpreted ones
(see :mod:`.residual`), so a :class:`CompiledResidual` is a drop-in
replacement for a :class:`~dynare_ct.codegen.residual.Residual`'s
callables.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import casadi as ca

from dynare_ct.codegen.errors import CodegenError
from dynare_ct.codegen.residual import Residual

__all__ = ["CompiledResidual", "compile_residual"]

_LIB_SUFFIX = {"linux": ".so", "darwin": ".dylib", "win32": ".dll"}.get(sys.platform, ".so")


@dataclass
class CompiledResidual:
    """Natively-compiled residual and Jacobians, with their on-disk artifacts."""

    function: ca.Function
    jacobian_x: ca.Function
    jacobian_xdot: ca.Function
    source: Path
    library: Path


def compile_residual(
    residual: Residual,
    *,
    name: str = "model",
    directory: str | Path | None = None,
    compiler: str | None = None,
    optimize: bool = True,
) -> CompiledResidual:
    """Generate C for ``residual``, compile it, and load the functions back.

    ``directory`` is where the ``.c`` source and shared library are written
    (a fresh temporary directory by default — pass a stable path to cache
    the artifact across runs). ``compiler`` defaults to ``$CC`` or ``gcc``.
    """
    if directory is not None:
        workdir = Path(directory)
    else:
        workdir = Path(tempfile.mkdtemp(prefix="dynare_ct_"))
    workdir.mkdir(parents=True, exist_ok=True)
    source = workdir / f"{name}.c"
    library = workdir / f"{name}{_LIB_SUFFIX}"

    generator = ca.CodeGenerator(source.name)
    generator.add(residual.function)
    generator.add(residual.jacobian_x)
    generator.add(residual.jacobian_xdot)
    generator.generate(f"{workdir}{os.sep}")

    _compile(source, library, compiler, optimize)

    return CompiledResidual(
        function=ca.external(residual.function.name(), str(library)),
        jacobian_x=ca.external(residual.jacobian_x.name(), str(library)),
        jacobian_xdot=ca.external(residual.jacobian_xdot.name(), str(library)),
        source=source,
        library=library,
    )


def _compile(source: Path, library: Path, compiler: str | None, optimize: bool) -> None:
    cc = compiler or os.environ.get("CC") or "gcc"
    flags = ["-fPIC", "-shared"]
    if optimize:
        flags.insert(0, "-O3")
    command = [cc, str(source), "-o", str(library), *flags]
    try:
        result = subprocess.run(command, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise CodegenError(f"C compiler {cc!r} not found; install one or set $CC") from exc
    if result.returncode != 0:
        raise CodegenError(f"compiling {source.name} failed:\n{result.stderr.strip()}")

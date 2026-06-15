"""Programmatic API: load a model and simulate it.

:func:`parse` runs the whole front end — macro expansion, parsing, and IR
construction — and returns a :class:`Model`, the user-facing handle whose
:meth:`Model.simul` and :meth:`Model.steady_state` call the solver. This
is the layer the CLI wraps; CasADi and the internal IR are not exposed.

    import continuo
    model = continuo.parse("model.mod")
    sol = model.simul()                 # reads the simulate command
"""

from __future__ import annotations

from pathlib import Path

from continuo import ir
from continuo.io.solution import Solution
from continuo.macro import expand, expand_string
from continuo.parser import parse as _parse_text
from continuo.solve import LinearSolver, simulate, steady_state

__all__ = ["Model", "parse", "parse_string"]


class Model:
    """A loaded model: its symbol table and the solver entry points."""

    def __init__(self, model: ir.Model):
        self._model = model

    # -- inspection ---------------------------------------------------------

    @property
    def states(self) -> tuple[str, ...]:
        return self._model.states

    @property
    def jumps(self) -> tuple[str, ...]:
        return self._model.jumps

    @property
    def algebraic(self) -> tuple[str, ...]:
        return self._model.algebraic

    @property
    def endogenous(self) -> tuple[str, ...]:
        return self._model.endogenous

    @property
    def exogenous(self) -> tuple[str, ...]:
        return self._model.exogenous

    @property
    def parameters(self) -> tuple[str, ...]:
        return self._model.parameters

    def __repr__(self) -> str:
        return (
            f"<continuo.Model: {len(self.endogenous)} endogenous "
            f"({len(self.states)} state, {len(self.jumps)} jump, "
            f"{len(self.algebraic)} algebraic), {len(self.parameters)} parameters>"
        )

    # -- solving ------------------------------------------------------------

    def steady_state(self, *, exogenous: dict[str, float] | None = None) -> dict[str, float]:
        """Compute the steady state at the given exogenous configuration."""
        return steady_state(self._model, exogenous=exogenous)

    def simul(
        self,
        *,
        horizon: float | None = None,
        intervals: int | None = None,
        scheme: str | None = None,
        solver: str | LinearSolver | None = None,
    ) -> Solution:
        """Run the perfect-foresight simulation, returning a :class:`Solution`.

        ``horizon`` / ``intervals`` / ``scheme`` override the model's
        ``simulate`` command. ``solver`` selects the linear backend: a
        preset name (``"superlu"``, ``"auto"``), a :class:`LinearSolver`
        instance, or ``None`` (the ``"auto"`` default).
        """
        return simulate(
            self._model, horizon=horizon, intervals=intervals, scheme=scheme, solver=solver
        )


def parse(path: str | Path) -> Model:
    """Load a ``.mod`` file (macro expansion, parsing, IR) into a :class:`Model`."""
    text, _linemap = expand(path)
    return Model(ir.build(_parse_text(text)))


def parse_string(source: str, *, base_dir: str | Path | None = None) -> Model:
    """Load model source given as a string into a :class:`Model`."""
    text, _linemap = expand_string(source, base_dir=base_dir)
    return Model(ir.build(_parse_text(text)))

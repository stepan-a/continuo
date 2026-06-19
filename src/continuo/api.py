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
from continuo.solve import (
    LinearSolver,
    SteadySolver,
    simulate,
    steady_state,
)

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

    def steady_state(
        self,
        *,
        exogenous: dict[str, float] | None = None,
        solver: str | SteadySolver | None = None,
        options: dict[str, object] | None = None,
        nodomain: bool | None = None,
    ) -> dict[str, float]:
        """Compute the steady state at the given exogenous configuration.

        ``solver`` selects the nonlinear algorithm for the numerical path: a
        preset name (``"newton"``, ``"hybr"``, ``"kinsol"``, ``"homotopy"``,
        …), a :class:`SteadySolver` instance, or ``None`` — which falls back
        to the model's ``steady(solver=…)`` directive, then to ``"auto"``.
        ``options`` configures a named preset (e.g. ``{"strategy": "picard"}``
        for ``kinsol``); when both are omitted, the directive's ``solver`` and
        ``options`` are used. ``nodomain`` disables the domain change of
        variable (solve in raw ``x`` despite declared constraints); ``None``
        defers to the model's ``steady(nodomain)`` directive, an explicit
        bool overrides it.
        """
        return steady_state(
            self._model,
            exogenous=exogenous,
            solver=solver,
            options=options,
            nodomain=nodomain,
        )

    def simul(
        self,
        *,
        horizon: float | None = None,
        intervals: int | None = None,
        scheme: str | None = None,
        order: int | None = None,
        adapt: float | None = None,
        monitor: str | None = None,
        solver: str | LinearSolver | None = None,
        steady_solver: str | SteadySolver | None = None,
        steady_solver_options: dict[str, object] | None = None,
    ) -> Solution:
        """Run the perfect-foresight simulation, returning a :class:`Solution`.

        ``horizon`` / ``intervals`` / ``scheme`` / ``order`` override the
        model's ``simulate`` command; ``order`` selects the collocation order
        of a multi-stage ``scheme`` (the family default when ``None``).
        ``adapt`` turns on adaptive mesh refinement to the given error
        tolerance, driven by ``monitor`` (``"residual"`` by default, or
        ``"richardson"``); both override the directive. ``solver`` selects the linear backend: a
        preset name (``"superlu"``, ``"auto"``), a :class:`LinearSolver`
        instance, or ``None`` (the ``"auto"`` default). ``steady_solver``
        selects the nonlinear algorithm for the internal steady-state solves,
        overriding the ``steady(solver=…)`` directive, and
        ``steady_solver_options`` configures it.
        """
        return simulate(
            self._model,
            horizon=horizon,
            intervals=intervals,
            scheme=scheme,
            order=order,
            adapt=adapt,
            monitor=monitor,
            solver=solver,
            steady_solver=steady_solver,
            steady_solver_options=steady_solver_options,
        )


def parse(path: str | Path) -> Model:
    """Load a ``.mod`` file (macro expansion, parsing, IR) into a :class:`Model`."""
    text, _linemap = expand(path)
    return Model(ir.build(_parse_text(text)))


def parse_string(source: str, *, base_dir: str | Path | None = None) -> Model:
    """Load model source given as a string into a :class:`Model`."""
    text, _linemap = expand_string(source, base_dir=base_dir)
    return Model(ir.build(_parse_text(text)))

"""Simulation orchestrator: from a model to a solved path.

:func:`simulate` reads the model's ``simulate`` command (horizon ``T``,
grid ``N``, scheme), builds the exogenous belief paths from the ``shocks``
block, and runs the perfect-foresight solve, returning a path over
``[0, T]``.

Revelation structure. The reveal times across all shocks partition
``[0, T]`` into segments. Within a segment, each shock's *active* belief
is the latest one revealed at or before the segment's start. Each segment
is solved as its own perfect-foresight problem over a fresh horizon of
length ``T`` — segment ``i`` is solved on ``[tᵢ, tᵢ + T]``, believing its
beliefs hold forever, with the jumps anchored at the steady state reached
at ``tᵢ + T``. The state at ``tᵢ`` is carried continuously from the
previous segment (states cannot jump; jumps re-optimise at the surprise).
Only the realised slice ``[tᵢ, tᵢ₊₁)`` of each segment is kept; the
reported path covers ``[0, T]``.

Reveal times are snapped to the grid (spacing ``dt = T/N``) so the
segment grids align and the realised slices splice without
interpolation.
"""

from __future__ import annotations

import casadi as ca
import numpy as np

from continuo.codegen.errors import CodegenError
from continuo.codegen.residual import build_residual
from continuo.codegen.translate import SymbolTable, translate
from continuo.io.solution import Segment, Solution
from continuo.ir.model import Model
from continuo.parser.ast import Expr
from continuo.solve.disc import uniform_grid
from continuo.solve.errors import SolveError
from continuo.solve.numeric import constant_table, eval_constant
from continuo.solve.pf import initial_conditions, solve_segment
from continuo.solve.steady import evaluate_parameters, steady_state

__all__ = ["simulate"]

_SUPPORTED_SCHEME = "crank_nicolson"


def simulate(
    model: Model,
    *,
    horizon: float | None = None,
    intervals: int | None = None,
    scheme: str | None = None,
) -> Solution:
    """Solve the model's perfect-foresight transition, returning a Solution.

    ``horizon`` / ``intervals`` / ``scheme`` override the ``simulate``
    command; if both ``horizon`` and ``intervals`` are omitted the command
    must supply them.
    """
    theta = evaluate_parameters(model)
    horizon, intervals, scheme = _resolve_command(model, theta, horizon, intervals, scheme)
    if scheme != _SUPPORTED_SCHEME:
        raise SolveError(f"discretisation scheme {scheme!r} is not implemented yet")

    residual = build_residual(model)
    dt = horizon / intervals
    param_symbols = {name: ca.SX(value) for name, value in theta.items()}
    schedule = _schedule(model, theta, dt)
    starts = _segment_starts(schedule, intervals)

    index = {name: k for k, name in enumerate(model.endogenous)}
    segments: list[Segment] = []
    carried: dict[str, float] | None = None

    for s, start_index in enumerate(starts):
        end_index = starts[s + 1] if s + 1 < len(starts) else intervals + 1
        start_time = start_index * dt
        exogenous_at = _active_exogenous(schedule, start_index, param_symbols)
        grid = uniform_grid(horizon, intervals, start=start_time)

        terminal_ss = steady_state(model, exogenous=exogenous_at(start_time + horizon))
        if carried is None:
            initial_ss = steady_state(model, exogenous=exogenous_at(start_time))
            initial_states = initial_conditions(model, theta, exogenous_at(start_time), initial_ss)
        else:
            initial_states = carried
        terminal_jumps = {name: terminal_ss[name] for name in model.jumps}
        guess = np.tile([terminal_ss[name] for name in model.endogenous], (intervals + 1, 1))

        segment_path, iterations = solve_segment(
            model,
            residual,
            grid,
            theta=theta,
            exogenous_at=exogenous_at,
            initial_states=initial_states,
            terminal_jumps=terminal_jumps,
            guess=guess,
        )

        realised = end_index - start_index
        segments.append(
            Segment(
                start_time=start_time,
                times=grid.points[:realised],
                path=segment_path[:realised],
                names=model.endogenous,
                info_set=exogenous_at(start_time),
                terminal_ss=terminal_ss,
                iterations=iterations,
            )
        )
        if end_index <= intervals:  # carry the state into the next segment
            carried = {name: segment_path[realised, index[name]] for name in model.states}

    diagnostics = {
        "scheme": scheme,
        "segments": len(segments),
        "newton_iterations": sum(segment.iterations for segment in segments),
    }
    return Solution(tuple(segments), model.endogenous, diagnostics)


# ---------------------------------------------------------------------------
# command and revelation schedule
# ---------------------------------------------------------------------------


def _resolve_command(
    model: Model,
    theta: dict[str, float],
    horizon: float | None,
    intervals: int | None,
    scheme: str | None,
) -> tuple[float, int, str]:
    if horizon is not None and intervals is not None:
        return float(horizon), int(intervals), scheme or _SUPPORTED_SCHEME
    if not model.simulations:
        raise SolveError("no simulate command in the model; pass horizon and intervals")
    command = model.simulations[0]
    table = constant_table(theta, {}, model)
    t = eval_constant(command.horizon, table, what="simulate horizon T")
    n = eval_constant(command.grid, table, what="simulate grid N")
    return float(t), int(n), scheme or command.scheme


def _schedule(
    model: Model, theta: dict[str, float], dt: float
) -> dict[str, list[tuple[int, Expr]]]:
    """For each shock, its beliefs as ``(grid-snapped reveal index, path expr)``, sorted."""
    table = constant_table(theta, {}, model)
    schedule: dict[str, list[tuple[int, Expr]]] = {}
    for shock in model.shocks:
        entries = []
        for path in shock.paths:
            reveal = eval_constant(path.reveal_time, table, what=f"reveal time of {shock.name!r}")
            entries.append((round(reveal / dt), path.path))
        schedule[shock.name] = sorted(entries, key=lambda entry: entry[0])
    return schedule


def _segment_starts(schedule: dict[str, list[tuple[int, Expr]]], intervals: int) -> list[int]:
    """Grid indices at which the active belief set changes (always includes 0)."""
    starts = {0}
    for entries in schedule.values():
        starts.update(index for index, _ in entries if 0 < index < intervals)
    return sorted(starts)


def _active_exogenous(
    schedule: dict[str, list[tuple[int, Expr]]], start_index: int, param_symbols: dict[str, ca.SX]
):
    """Build ``exogenous_at(t)`` from each shock's belief active at ``start_index``."""
    active: dict[str, Expr] = {}
    for name, entries in schedule.items():
        chosen: Expr | None = None
        for reveal_index, expr in entries:  # ascending
            if reveal_index <= start_index:
                chosen = expr
            else:
                break
        if chosen is not None:
            active[name] = chosen

    def exogenous_at(t: float) -> dict[str, float]:
        return {name: _belief_value(expr, param_symbols, t) for name, expr in active.items()}

    return exogenous_at


def _belief_value(expr: Expr, param_symbols: dict[str, ca.SX], t: float) -> float:
    table = SymbolTable(symbols=dict(param_symbols), in_shock_path=True)
    table.symbols["t"] = ca.SX(t)
    try:
        return float(ca.evalf(translate(expr, table)))
    except CodegenError as exc:
        raise SolveError(f"shock path: {exc}") from None

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

Each segment's grid forces an exact node at its realised boundary — the
next reveal time, or the terminal time ``T`` for the last segment — so a
reveal that falls between equally-spaced nodes is no longer snapped (and
smeared by up to one ``dt``); the realised slices splice without
interpolation.
"""

from __future__ import annotations

import logging

import casadi as ca
import numpy as np

from continuo.codegen.errors import CodegenError
from continuo.codegen.residual import build_residual
from continuo.codegen.translate import SymbolTable, translate
from continuo.io.solution import Segment, Solution
from continuo.ir.model import Model
from continuo.parser.ast import Expr
from continuo.solve.disc import (
    SCHEMES,
    aligned_grid,
    equidistribution_ratio,
)
from continuo.solve.errors import SolveError
from continuo.solve.linsolve import LinearSolver, select_solver
from continuo.solve.numeric import constant_table, eval_constant
from continuo.solve.pf import SolveStats, initial_conditions, solve_segment
from continuo.solve.refine import ADAPT_MONITORS, refine_segment
from continuo.solve.rootfind import SteadySolver, select_steady_solver
from continuo.solve.steady import (
    directive_solver,
    directive_solver_options,
    evaluate_parameters,
    steady_state,
)

__all__ = ["simulate"]

_DEFAULT_SCHEME = "crank_nicolson"

# Coupling stencil each scheme generates, which guides ``solver="auto"``:
# CN and the collocation families are all one-step (each interval couples only
# its endpoints and its own stages), so the stacked Jacobian is block-triangular.
_STENCIL = dict.fromkeys(SCHEMES, "one-step")

logger = logging.getLogger(__name__)


def simulate(
    model: Model,
    *,
    horizon: float | None = None,
    intervals: int | None = None,
    scheme: str | None = None,
    order: int | None = None,
    adapt: float | None = None,
    monitor: str = "richardson",
    solver: str | LinearSolver | None = None,
    steady_solver: str | SteadySolver | None = None,
    steady_solver_options: dict[str, object] | None = None,
) -> Solution:
    """Solve the model's perfect-foresight transition, returning a Solution.

    ``horizon`` / ``intervals`` / ``scheme`` override the ``simulate``
    command; if both ``horizon`` and ``intervals`` are omitted the command
    must supply them. ``order`` selects the collocation order for the
    multi-stage families (ignored by ``crank_nicolson``; the family default
    is used when ``None``). ``adapt`` turns on adaptive mesh refinement: each
    segment is refined (curvature-equidistributed) and re-solved until the
    ``monitor`` error estimate falls below this tolerance — ``monitor`` is
    ``"richardson"`` (default, a calibrated magnitude) or ``"residual"``.
    ``solver`` selects the linear backend (preset name,
    :class:`LinearSolver` instance, or the ``"auto"`` default).
    ``steady_solver`` selects the nonlinear algorithm for the internal
    steady-state solves (the terminal anchor and the initial state),
    overriding the ``steady(solver=…)`` directive; ``None`` falls back to
    that directive, then to ``"auto"``. ``steady_solver_options`` configures
    it (e.g. ``{"strategy": "picard"}``), overriding the directive's
    ``options={…}``.
    """
    theta = evaluate_parameters(model)
    horizon, intervals, scheme, order, solver = _resolve_command(
        model, theta, horizon, intervals, scheme, order, solver
    )
    if steady_solver is None:
        steady_solver = directive_solver(model)
        if steady_solver_options is None:
            steady_solver_options = directive_solver_options(model)
    # Resolve the steady backend once (validates name/options) and reuse the
    # instance for every internal steady-state solve.
    steady_backend = select_steady_solver(steady_solver, options=steady_solver_options)
    if scheme not in SCHEMES:
        raise SolveError(f"discretisation scheme {scheme!r} is not implemented yet")
    if adapt is not None and monitor not in ADAPT_MONITORS:
        raise SolveError(
            f"adaptive refinement needs an error-estimating monitor "
            f"({' or '.join(ADAPT_MONITORS)}), got {monitor!r}"
        )
    # One backend for the whole run; auto routes by the scheme's coupling stencil.
    linear = select_solver(solver, stencil=_STENCIL[scheme])

    residual = build_residual(model)
    param_symbols = {name: ca.SX(value) for name, value in theta.items()}
    schedule = _schedule(model, theta)
    starts = _segment_starts(schedule, horizon)

    index = {name: k for k, name in enumerate(model.endogenous)}
    segments: list[Segment] = []
    carried: dict[str, float] | None = None
    # The stacked Jacobian's pattern depends only on (N, n, scheme, order), not
    # on the node positions, so it is identical across segments even when each
    # uses a different shock-aligned mesh: analyse once, reuse the factorisation.
    sym: object | None = None
    num: object | None = None
    stats = SolveStats()

    for s, start_time in enumerate(starts):
        last = s + 1 == len(starts)
        # Each segment is solved over a full horizon from its start; the next
        # reveal (or the terminal time T, for the last segment) is forced to be
        # an exact node, so a reveal between nodes is no longer snapped/smeared.
        mark = horizon if last else starts[s + 1]
        exogenous_at = _active_exogenous(schedule, start_time, param_symbols)

        terminal_ss = steady_state(
            model, exogenous=exogenous_at(start_time + horizon), solver=steady_backend
        )
        if carried is None:
            initial_ss = steady_state(
                model, exogenous=exogenous_at(start_time), solver=steady_backend
            )
            initial_states = initial_conditions(
                model, theta, exogenous_at(start_time), initial_ss, steady_solver=steady_backend
            )
        else:
            initial_states = carried
        terminal_jumps = {name: terminal_ss[name] for name in model.jumps}
        terminal_row = np.array([terminal_ss[name] for name in model.endogenous])

        if adapt is None:
            grid, mark_index = aligned_grid(start_time, horizon, intervals, mark)
            segment_path, iterations, sym, num = solve_segment(
                model,
                residual,
                grid,
                theta=theta,
                exogenous_at=exogenous_at,
                initial_states=initial_states,
                terminal_jumps=terminal_jumps,
                guess=np.tile(terminal_row, (intervals + 1, 1)),
                solver=linear,
                scheme=scheme,
                order=order,
                sym=sym,
                num=num,
                stats=stats,
            )
        else:
            # Adaptive meshes differ per segment, so the cross-segment warm-start
            # does not apply; each refinement pass re-analyses its own mesh.
            grid, mark_index, segment_path, iterations = refine_segment(
                model=model,
                residual=residual,
                theta=theta,
                exogenous_at=exogenous_at,
                initial_states=initial_states,
                terminal_jumps=terminal_jumps,
                terminal_row=terminal_row,
                scheme=scheme,
                order=order,
                solver=linear,
                stats=stats,
                start=start_time,
                horizon=horizon,
                intervals=intervals,
                mark=mark,
                tol=adapt,
                monitor=monitor,
            )

        # Last segment keeps the mark node (the terminal time); others stop just
        # before the next reveal and carry that node's state into the next.
        realised = mark_index + 1 if last else mark_index
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
        if not last:  # carry the state at the exact reveal node into the next segment
            carried = {name: segment_path[mark_index, index[name]] for name in model.states}

    solution = Solution(tuple(segments), model.endogenous, {})
    diagnostics = {
        "scheme": scheme,
        "segments": len(segments),
        "newton_iterations": sum(segment.iterations for segment in segments),
        "solver": linear.name,
        # Cheap grid-adequacy hint: ~1 balanced, >>1 resolution misallocated.
        "equidistribution_ratio": equidistribution_ratio(solution.t, solution.path),
        **stats.as_dict(),
    }
    solution.diagnostics.update(diagnostics)
    logger.info(
        "simulated %d segment(s), %d Newton iteration(s) total (%s); "
        "%s: %d factor(s), %d refactor(s)%s",
        diagnostics["segments"],
        diagnostics["newton_iterations"],
        diagnostics["scheme"],
        linear.name,
        stats.factorizations,
        stats.refactorizations,
        f", {stats.refactor_fallbacks} fallback(s)" if stats.refactor_fallbacks else "",
    )
    return solution


# ---------------------------------------------------------------------------
# command and revelation schedule
# ---------------------------------------------------------------------------


def _resolve_command(
    model: Model,
    theta: dict[str, float],
    horizon: float | None,
    intervals: int | None,
    scheme: str | None,
    order: int | None,
    solver: str | LinearSolver | None,
) -> tuple[float, int, str, int | None, str | LinearSolver | None]:
    # Precedence for scheme/order/solver: explicit argument > simulate directive > default.
    if horizon is not None and intervals is not None:
        return float(horizon), int(intervals), scheme or _DEFAULT_SCHEME, order, solver
    if not model.simulations:
        raise SolveError("no simulate command in the model; pass horizon and intervals")
    command = model.simulations[0]
    table = constant_table(theta, {}, model)
    t = eval_constant(command.horizon, table, what="simulate horizon T")
    n = eval_constant(command.grid, table, what="simulate grid N")
    chosen_solver = solver if solver is not None else command.solver
    chosen_order = order if order is not None else command.order
    return float(t), int(n), scheme or command.scheme, chosen_order, chosen_solver


def _schedule(model: Model, theta: dict[str, float]) -> dict[str, list[tuple[float, Expr]]]:
    """For each shock, its beliefs as ``(exact reveal time, path expr)``, sorted by time."""
    table = constant_table(theta, {}, model)
    schedule: dict[str, list[tuple[float, Expr]]] = {}
    for shock in model.shocks:
        entries = []
        for path in shock.paths:
            reveal = eval_constant(path.reveal_time, table, what=f"reveal time of {shock.name!r}")
            entries.append((reveal, path.path))
        schedule[shock.name] = sorted(entries, key=lambda entry: entry[0])
    return schedule


def _segment_starts(schedule: dict[str, list[tuple[float, Expr]]], horizon: float) -> list[float]:
    """Times at which the active belief set changes (always includes 0)."""
    starts = {0.0}
    for entries in schedule.values():
        starts.update(t for t, _ in entries if 0.0 < t < horizon)
    return sorted(starts)


def _active_exogenous(
    schedule: dict[str, list[tuple[float, Expr]]],
    start_time: float,
    param_symbols: dict[str, ca.SX],
):
    """Build ``exogenous_at(t)`` from each shock's belief active at ``start_time``."""
    active: dict[str, Expr] = {}
    for name, entries in schedule.items():
        chosen: Expr | None = None
        for reveal_time, expr in entries:  # ascending
            if reveal_time <= start_time:
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

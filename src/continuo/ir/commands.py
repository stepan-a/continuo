"""Command validation: the simulate and steady directives.

``simulate(T=…, N=…[, scheme=…])`` runs a perfect-foresight solve: the
horizon ``T`` (a positive real) and grid resolution ``N`` (a positive
integer number of intervals) are mandatory keyword arguments, ``scheme``
is an optional discretisation scheme (default ``crank_nicolson``), and no
other options exist in v1.

``steady[(t=…[, e={…}])]`` evaluates a steady state for inspection: bare
``steady;`` means ``t = T`` under the final information set, ``t`` selects
a point on the horizon (non-negative), and ``e={…}`` overrides exogenous
values. The ``t > T`` out-of-range check needs the horizon and is left to
the orchestrator.
"""

from __future__ import annotations

from dataclasses import replace

from continuo.ir.errors import IRError
from continuo.ir.model import Model, Simulation, SteadyQuery
from continuo.parser.ast import (
    DictLiteral,
    Expr,
    Identifier,
    ModelFile,
    NumberLit,
    SimulateCommand,
    SteadyCommand,
    StringLit,
    UnaryOp,
)

__all__ = ["attach_commands"]

# Discretisation schemes the language recognises (not all are implemented
# in the solver yet); validating against the set catches typos.
_SCHEMES = {"crank_nicolson", "radau", "sdirk", "lobatto_iiia"}
_DEFAULT_SCHEME = "crank_nicolson"

# Linear-solver presets the directive recognises (mirrors solve.SOLVERS plus
# "auto"); whether a named backend is actually available is checked at solve time.
_SOLVERS = {"auto", "superlu", "klu", "klu-nobtf", "umfpack", "pardiso"}


def attach_commands(model: Model, model_file: ModelFile) -> Model:
    """Validate the simulate / steady commands and attach them to the model."""
    simulations: list[Simulation] = []
    steady_queries: list[SteadyQuery] = []
    for stmt in model_file.statements:
        if isinstance(stmt, SimulateCommand):
            simulations.append(_simulate(stmt))
        elif isinstance(stmt, SteadyCommand):
            steady_queries.append(_steady(stmt))
    return replace(
        model,
        simulations=tuple(simulations),
        steady_queries=tuple(steady_queries),
    )


# ---------------------------------------------------------------------------
# simulate
# ---------------------------------------------------------------------------


def _simulate(cmd: SimulateCommand) -> Simulation:
    if cmd.args:
        raise IRError("simulate takes keyword arguments only (T=…, N=…)", cmd.pos)
    options = _collect(cmd.kwargs, allowed=("T", "N", "scheme", "solver"), what="simulate")
    if "T" not in options:
        raise IRError("simulate requires the horizon T", cmd.pos)
    if "N" not in options:
        raise IRError("simulate requires the grid resolution N", cmd.pos)
    _check_positive("T", options["T"], integer=False)
    _check_positive("N", options["N"], integer=True)
    return Simulation(
        options["T"],
        options["N"],
        _scheme(options.get("scheme")),
        _solver(options.get("solver")),
    )


def _scheme(value: Expr | None) -> str:
    if value is None:
        return _DEFAULT_SCHEME
    if not isinstance(value, Identifier):
        raise IRError(
            "simulate scheme must be a scheme name (e.g. scheme=crank_nicolson)",
            getattr(value, "pos", None),
        )
    if value.name not in _SCHEMES:
        raise IRError(
            f"unknown discretisation scheme {value.name!r}; expected one of "
            f"{', '.join(sorted(_SCHEMES))}",
            value.pos,
        )
    return value.name


def _solver(value: Expr | None) -> str | None:
    """A solver preset named as a bare identifier or a string (for ``klu-nobtf``)."""
    if value is None:
        return None
    if isinstance(value, Identifier):
        name = value.name
    elif isinstance(value, StringLit):
        name = value.value
    else:
        raise IRError(
            "simulate solver must be a solver name (e.g. solver=klu)",
            getattr(value, "pos", None),
        )
    if name not in _SOLVERS:
        raise IRError(
            f"unknown linear solver {name!r}; expected one of {', '.join(sorted(_SOLVERS))}",
            getattr(value, "pos", None),
        )
    return name


def _check_positive(name: str, expr: Expr, *, integer: bool) -> None:
    value = _literal(expr)
    if value is None:  # a parameter or expression; checked once evaluated
        return
    kind = "a positive integer" if integer else "positive"
    if value <= 0 or (integer and value != int(value)):
        raise IRError(f"simulate {name} must be {kind}", getattr(expr, "pos", None))


# ---------------------------------------------------------------------------
# steady
# ---------------------------------------------------------------------------


def _steady(cmd: SteadyCommand) -> SteadyQuery:
    if cmd.args:
        raise IRError("steady takes keyword arguments only (t=…, e={…})", cmd.pos)
    options = _collect(cmd.kwargs, allowed=("t", "e"), what="steady")
    time = options.get("t")
    if time is not None:
        value = _literal(time)
        if value is not None and value < 0:
            raise IRError("steady t must be non-negative", getattr(time, "pos", None))
    exogenous = options.get("e")
    if exogenous is not None and not isinstance(exogenous, DictLiteral):
        raise IRError("steady 'e' must be a {…} mapping", getattr(exogenous, "pos", None))
    return SteadyQuery(time, exogenous)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _collect(kwargs: list, *, allowed: tuple[str, ...], what: str) -> dict[str, Expr]:
    options: dict[str, Expr] = {}
    for kw in kwargs:
        key = kw.name.name
        if key not in allowed:
            raise IRError(f"unknown {what} option {key!r}", kw.pos)
        if key in options:
            raise IRError(f"duplicate {what} option {key!r}", kw.pos)
        options[key] = kw.value
    return options


def _literal(expr: Expr) -> float | None:
    if isinstance(expr, NumberLit):
        return expr.value
    if isinstance(expr, UnaryOp) and expr.op == "-" and isinstance(expr.operand, NumberLit):
        return -expr.operand.value
    return None

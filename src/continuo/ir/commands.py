"""Command validation: the simulate and steady directives.

``simulate(T=…, N=…[, scheme=…])`` runs a perfect-foresight solve: the
horizon ``T`` (a positive real) and grid resolution ``N`` (a positive
integer number of intervals) are mandatory keyword arguments, ``scheme``
is an optional discretisation scheme (default ``crank_nicolson``), and no
other options exist in v1.

``steady[(t=…[, e={…}][, solver=…])]`` evaluates a steady state for
inspection: bare ``steady;`` means ``t = T`` under the final information
set, ``t`` selects a point on the horizon (non-negative), ``e={…}``
overrides exogenous values, and ``solver`` names the nonlinear algorithm
(see :mod:`continuo.solve.rootfind`). The ``t > T`` out-of-range check
needs the horizon and is left to the orchestrator.
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

# Discretisation schemes the language recognises; validating against the set
# catches typos. Mirrors continuo.solve.disc.SCHEMES.
_SCHEMES = {"crank_nicolson", "gauss", "radau", "lobatto_iiia"}
_DEFAULT_SCHEME = "crank_nicolson"

# Collocation orders each family provides (mirrors solve.disc.SCHEME_ORDERS);
# crank_nicolson is fixed second-order and takes no order argument.
_SCHEME_ORDERS = {
    "gauss": {2, 4, 6},
    "radau": {1, 3, 5},
    "lobatto_iiia": {2, 4, 6},
}

# Error monitors that can drive adaptive refinement (mirror solve.refine
# ADAPT_MONITORS); curvature is placement-only and cannot set a tolerance.
_MONITORS = {"richardson", "residual"}

# Linear-solver presets the simulate directive recognises (mirrors
# solve.SOLVERS plus "auto"); availability is checked at solve time.
_SOLVERS = {"auto", "superlu", "klu", "klu-nobtf", "umfpack", "pardiso"}

# Nonlinear steady-state solver presets the steady directive recognises
# (mirrors solve.rootfind.STEADY_SOLVERS plus "auto"); availability (e.g.
# "kinsol" needing the CasADi plugin) is checked at solve time.
_STEADY_SOLVERS = {
    "auto",
    "newton",
    "hybr",
    "lm",
    "broyden",
    "krylov",
    "df-sane",
    "anderson",
    "kinsol",
    "homotopy",
}

# Bare positional flags the steady directive recognises.
_STEADY_FLAGS = {"nodomain"}


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
    options = _collect(
        cmd.kwargs,
        allowed=("T", "N", "scheme", "solver", "order", "adapt", "monitor"),
        what="simulate",
    )
    if "T" not in options:
        raise IRError("simulate requires the horizon T", cmd.pos)
    if "N" not in options:
        raise IRError("simulate requires the grid resolution N", cmd.pos)
    _check_positive("T", options["T"], integer=False)
    _check_positive("N", options["N"], integer=True)
    scheme = _scheme(options.get("scheme"))
    if "monitor" in options and "adapt" not in options:
        raise IRError(
            "simulate monitor requires adapt (e.g. adapt=1e-4)",
            getattr(options["monitor"], "pos", None),
        )
    return Simulation(
        options["T"],
        options["N"],
        scheme,
        _solver(options.get("solver")),
        _order(scheme, options.get("order")),
        _adapt(options.get("adapt")),
        _monitor(options.get("monitor")),
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


def _order(scheme: str, value: Expr | None) -> int | None:
    """The collocation order for ``scheme``; ``None`` when unspecified (family default)."""
    if value is None:
        return None
    n = _literal(value)
    if n is None or n <= 0 or n != int(n):
        raise IRError("simulate order must be a positive integer", getattr(value, "pos", None))
    if scheme == "crank_nicolson":
        raise IRError(
            "crank_nicolson is fixed second-order and takes no order; use "
            "scheme=gauss / radau / lobatto_iiia to choose an order",
            getattr(value, "pos", None),
        )
    allowed = _SCHEME_ORDERS[scheme]
    if int(n) not in allowed:
        raise IRError(
            f"{scheme} supports order in {{{', '.join(str(o) for o in sorted(allowed))}}}, "
            f"got {int(n)}",
            getattr(value, "pos", None),
        )
    return int(n)


def _adapt(value: Expr | None) -> Expr | None:
    """The adaptive-refinement tolerance expression; ``None`` when unspecified."""
    if value is None:
        return None
    literal = _literal(value)
    if literal is not None and literal <= 0:
        raise IRError("simulate adapt tolerance must be positive", getattr(value, "pos", None))
    return value


def _monitor(value: Expr | None) -> str | None:
    """The error monitor named as a bare identifier; ``None`` → the solver default."""
    if value is None:
        return None
    if not isinstance(value, Identifier):
        raise IRError(
            "simulate monitor must be a monitor name (e.g. monitor=richardson)",
            getattr(value, "pos", None),
        )
    if value.name not in _MONITORS:
        raise IRError(
            f"unknown error monitor {value.name!r}; expected one of {', '.join(sorted(_MONITORS))}",
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
    flags = _steady_flags(cmd.args)
    kwargs = _collect(cmd.kwargs, allowed=("t", "e", "solver", "options"), what="steady")
    time = kwargs.get("t")
    if time is not None:
        value = _literal(time)
        if value is not None and value < 0:
            raise IRError("steady t must be non-negative", getattr(time, "pos", None))
    exogenous = kwargs.get("e")
    if exogenous is not None and not isinstance(exogenous, DictLiteral):
        raise IRError("steady 'e' must be a {…} mapping", getattr(exogenous, "pos", None))
    if "options" in kwargs and "solver" not in kwargs:
        raise IRError(
            "steady options requires a solver (e.g. solver=kinsol)",
            getattr(kwargs["options"], "pos", None),
        )
    return SteadyQuery(
        time,
        exogenous,
        _steady_solver(kwargs.get("solver")),
        _steady_options(kwargs.get("options")),
        nodomain="nodomain" in flags,
    )


def _steady_flags(args: list[Expr]) -> set[str]:
    """Collect the bare positional flags of a steady directive (e.g. nodomain)."""
    flags: set[str] = set()
    for arg in args:
        if not isinstance(arg, Identifier) or arg.name not in _STEADY_FLAGS:
            name = arg.name if isinstance(arg, Identifier) else None
            raise IRError(
                f"unknown steady flag {name!r}"
                if name is not None
                else "steady positional arguments must be flags (e.g. nodomain)",
                getattr(arg, "pos", None),
            )
        if arg.name in flags:
            raise IRError(f"duplicate steady flag {arg.name!r}", arg.pos)
        flags.add(arg.name)
    return flags


def _steady_solver(value: Expr | None) -> str | None:
    """A steady-state solver preset named as a bare identifier or a string."""
    if value is None:
        return None
    if isinstance(value, Identifier):
        name = value.name
    elif isinstance(value, StringLit):
        name = value.value
    else:
        raise IRError(
            "steady solver must be a solver name (e.g. solver=newton)",
            getattr(value, "pos", None),
        )
    if name not in _STEADY_SOLVERS:
        raise IRError(
            f"unknown steady-state solver {name!r}; expected one of "
            f"{', '.join(sorted(_STEADY_SOLVERS))}",
            getattr(value, "pos", None),
        )
    return name


def _steady_options(value: Expr | None) -> dict[str, object] | None:
    """Parse ``options={key: literal, …}`` into a plain Python dict.

    Values are literals — a string, a number (kept as ``int`` when integral,
    else ``float``), or a bare identifier (taken as a string, so
    ``strategy = picard`` and ``strategy = "picard"`` are equivalent)."""
    if value is None:
        return None
    if not isinstance(value, DictLiteral):
        raise IRError("steady options must be a {…} mapping", getattr(value, "pos", None))
    result: dict[str, object] = {}
    for entry in value.entries:
        result[entry.key.name] = _option_value(entry.value)
    return result


def _option_value(expr: Expr) -> object:
    if isinstance(expr, StringLit):
        return expr.value
    if isinstance(expr, Identifier):
        return expr.name
    number = _literal(expr)  # NumberLit or negated NumberLit
    if number is not None:
        return int(number) if number == int(number) else number
    raise IRError(
        "steady options values must be strings, numbers or names",
        getattr(expr, "pos", None),
    )


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

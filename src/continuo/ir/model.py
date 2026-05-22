"""The Model: the semantic object the solvers consume.

A :class:`Model` is produced by :func:`continuo.ir.build.build` from a
parsed :class:`~continuo.parser.ast.ModelFile`. It carries the symbol
tables (variables grouped by class, exogenous processes, parameters),
the parameter-value expressions, and the model equations.

This is the v1 skeleton; boundary data (initval), shock segments, the
analytical steady state, command options, and the first-order reduction
of higher-order derivatives are added to it by later IR passes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from continuo.parser.ast import Equation, Expr, VarKind


@dataclass(frozen=True)
class ShockPath:
    """One (reveal time, expected path) belief for a shock.

    ``reveal_time`` is the instant agents adopt this belief (a literal 0
    for the bare ``path = …`` sugar); ``path`` is the believed exogenous
    path as an expression in the reserved time variable ``t``.
    """

    reveal_time: Expr
    path: Expr


@dataclass(frozen=True)
class Shock:
    """The belief sequence for one exogenous variable, ordered by reveal time."""

    name: str
    paths: tuple[ShockPath, ...]


@dataclass(frozen=True)
class Simulation:
    """A perfect-foresight run: horizon T, grid intervals N, and the scheme."""

    horizon: Expr
    grid: Expr
    scheme: str


@dataclass(frozen=True)
class SteadyQuery:
    """A steady-state inspection point.

    ``time`` is the point on the horizon to evaluate at (``None`` for the
    bare ``steady;`` default of ``t = T``); ``exogenous`` is an optional
    ``e={…}`` override expression.
    """

    time: Expr | None
    exogenous: Expr | None


@dataclass
class Model:
    """Symbol tables and equations of a continuous-time model.

    The four name sequences and ``parameters`` are kept in declaration
    order; ``parameter_values`` maps a parameter name to the (unevaluated)
    AST of its value.
    """

    states: tuple[str, ...] = ()
    jumps: tuple[str, ...] = ()
    algebraic: tuple[str, ...] = ()
    exogenous: tuple[str, ...] = ()
    parameters: tuple[str, ...] = ()
    parameter_values: dict[str, Expr] = field(default_factory=dict)
    equations: tuple[Equation, ...] = ()
    # Left-boundary data: state name -> initial-value expression (with the
    # auxiliary states keyed by their __aux_diff_ name). The solver's
    # optional starting iterate, keyed by endogenous variable.
    initial_values: dict[str, Expr] = field(default_factory=dict)
    initial_guess: dict[str, Expr] = field(default_factory=dict)
    # Analytical steady state x_ss = h(theta, e), endogenous name -> RHS
    # expression; empty when no steady_state_model block is given.
    steady_state: dict[str, Expr] = field(default_factory=dict)
    # Exogenous belief paths, one entry per varexo that the shocks block
    # drives; empty when no shocks block is given.
    shocks: tuple[Shock, ...] = ()
    # Validated simulate / steady commands, in source order.
    simulations: tuple[Simulation, ...] = ()
    steady_queries: tuple[SteadyQuery, ...] = ()

    @property
    def endogenous(self) -> tuple[str, ...]:
        """All endogenous variables in declaration order: states, jumps, algebraic."""
        return self.states + self.jumps + self.algebraic

    def kind_of(self, name: str) -> VarKind | None:
        """Return the class of an endogenous variable, or ``None`` if not endogenous."""
        if name in self.states:
            return VarKind.STATE
        if name in self.jumps:
            return VarKind.JUMP
        if name in self.algebraic:
            return VarKind.ALGEBRAIC
        return None

    def is_exogenous(self, name: str) -> bool:
        return name in self.exogenous

    def is_parameter(self, name: str) -> bool:
        return name in self.parameters

"""The Model: the semantic object the solvers consume.

A :class:`Model` is produced by :func:`dynare_ct.ir.build.build` from a
parsed :class:`~dynare_ct.parser.ast.ModelFile`. It carries the symbol
tables (variables grouped by class, exogenous processes, parameters),
the parameter-value expressions, and the model equations.

This is the v1 skeleton; boundary data (initval), shock segments, the
analytical steady state, command options, and the first-order reduction
of higher-order derivatives are added to it by later IR passes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dynare_ct.parser.ast import Equation, Expr, VarKind


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

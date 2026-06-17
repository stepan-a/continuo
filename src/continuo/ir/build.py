"""AST -> Model construction with semantic validation.

This pass turns a syntactically valid :class:`~continuo.parser.ast.ModelFile`
into a :class:`~continuo.ir.model.Model`, raising :class:`IRError` for the
semantic problems a grammar cannot catch.

It builds the symbol table — collecting the variable, exogenous and
parameter declarations (rejecting duplicates, cross-class name collisions
and use of the reserved ``__`` prefix), recording parameter values
(rejecting assignments to non-parameters), and gathering the model
block's equations. Classification checks, boundary/shock processing,
command validation and higher-order reduction are handled by separate
passes.
"""

from __future__ import annotations

from dataclasses import dataclass

from continuo.ir.boundary import attach_boundary
from continuo.ir.classify import classify
from continuo.ir.commands import attach_commands
from continuo.ir.constraints import attach_constraints
from continuo.ir.errors import IRError
from continuo.ir.model import Model
from continuo.ir.reduce import reduce_orders
from continuo.ir.shocks import attach_shocks
from continuo.ir.steady_state import attach_steady_state
from continuo.parser.ast import (
    Identifier,
    ModelBlock,
    ModelFile,
    ParameterDecl,
    ParameterValue,
    SourcePos,
    VarDecl,
    VarexoDecl,
    VarKind,
)

__all__ = ["build"]

# Names beginning with this prefix are reserved for IR-introduced auxiliary
# variables (e.g. higher-order-derivative reductions); users may not use them.
_RESERVED_PREFIX = "__"


@dataclass(frozen=True)
class _Decl:
    category: str  # human-readable: "state", "exogenous variable", "parameter", ...
    pos: SourcePos | None


def build(model_file: ModelFile) -> Model:
    """Build a :class:`Model` from a parsed ``.mod`` file.

    A file carrying equations is validated as a whole model (variable
    classification, square system); a declarations-only file (e.g. a
    shared parameter fragment) is built without those whole-model checks.
    """
    model = _Builder().run(model_file)
    if model.equations:
        model = reduce_orders(model)
        classify(model)
        model = attach_boundary(model, model_file)
        model = attach_steady_state(model, model_file)
        model = attach_constraints(model, model_file)
        model = attach_shocks(model, model_file)
        model = attach_commands(model, model_file)
    return model


class _Builder:
    def __init__(self) -> None:
        self._declared: dict[str, _Decl] = {}
        self._states: list[str] = []
        self._jumps: list[str] = []
        self._algebraic: list[str] = []
        self._exogenous: list[str] = []
        self._parameters: list[str] = []
        self._parameter_values: dict[str, object] = {}
        self._equations: list = []
        self._model_seen = False

    def run(self, model_file: ModelFile) -> Model:
        # First collect every declaration so parameter values and (later)
        # equations can be validated against the complete symbol table.
        for stmt in model_file.statements:
            if isinstance(stmt, VarDecl):
                self._collect_vars(stmt)
            elif isinstance(stmt, VarexoDecl):
                self._collect_exogenous(stmt)
            elif isinstance(stmt, ParameterDecl):
                self._collect_parameters(stmt)
        # Then everything that refers to declared names.
        for stmt in model_file.statements:
            if isinstance(stmt, ParameterValue):
                self._collect_parameter_value(stmt)
            elif isinstance(stmt, ModelBlock):
                self._collect_model(stmt)
        return Model(
            states=tuple(self._states),
            jumps=tuple(self._jumps),
            algebraic=tuple(self._algebraic),
            exogenous=tuple(self._exogenous),
            parameters=tuple(self._parameters),
            parameter_values=self._parameter_values,
            equations=tuple(self._equations),
        )

    # -- declarations -------------------------------------------------------

    _KIND_BUCKET = {
        VarKind.STATE: "_states",
        VarKind.JUMP: "_jumps",
        VarKind.ALGEBRAIC: "_algebraic",
    }

    def _collect_vars(self, decl: VarDecl) -> None:
        bucket = getattr(self, self._KIND_BUCKET[decl.kind])
        for ident in decl.names:
            self._declare(ident, decl.kind.value)
            bucket.append(ident.name)

    def _collect_exogenous(self, decl: VarexoDecl) -> None:
        for ident in decl.names:
            self._declare(ident, "exogenous variable")
            self._exogenous.append(ident.name)

    def _collect_parameters(self, decl: ParameterDecl) -> None:
        for ident in decl.names:
            self._declare(ident, "parameter")
            self._parameters.append(ident.name)

    def _declare(self, ident: Identifier, category: str) -> None:
        name = ident.name
        if name.startswith(_RESERVED_PREFIX):
            raise IRError(
                f"name {name!r} is reserved (the {_RESERVED_PREFIX!r} prefix is "
                "used for compiler-introduced variables)",
                ident.pos,
            )
        prior = self._declared.get(name)
        if prior is not None:
            raise IRError(
                f"{name!r} is already declared as {prior.category}",
                ident.pos,
            )
        self._declared[name] = _Decl(category, ident.pos)

    # -- parameter values ---------------------------------------------------

    def _collect_parameter_value(self, pv: ParameterValue) -> None:
        name = pv.name.name
        decl = self._declared.get(name)
        if decl is None:
            raise IRError(f"assignment to undeclared parameter {name!r}", pv.name.pos)
        if decl.category != "parameter":
            raise IRError(
                f"cannot assign a value to {name!r}: it is a {decl.category}, "
                "only parameters take values",
                pv.name.pos,
            )
        if name in self._parameter_values:
            raise IRError(f"duplicate value for parameter {name!r}", pv.name.pos)
        self._parameter_values[name] = pv.value

    # -- model block --------------------------------------------------------

    def _collect_model(self, block: ModelBlock) -> None:
        if self._model_seen:
            raise IRError("more than one model block", block.pos)
        self._model_seen = True
        self._equations.extend(block.equations)

"""AST node dataclasses for the dynare-ct parser.

Covers declarations (var / varexo / parameters), parameter-value
assignments, and the expression sub-grammar (arithmetic, comparison,
logical, unary, function calls). New node types land as the grammar
grows to encompass the model block, initval, shocks, etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class VarKind(Enum):
    """Endogenous variable classification — see DESIGN, "Variable classification"."""

    STATE = "state"
    JUMP = "jump"
    ALGEBRAIC = "algebraic"


@dataclass(frozen=True)
class SourcePos:
    """Position in the post-macroexpansion source text (1-indexed)."""

    line: int
    column: int


# ---------------------------------------------------------------------------
# Expressions
# ---------------------------------------------------------------------------


@dataclass
class Identifier:
    name: str
    pos: SourcePos | None = None


@dataclass
class NumberLit:
    value: float
    pos: SourcePos | None = None


@dataclass
class UnaryOp:
    op: str  # "-", "!"
    operand: Expr
    pos: SourcePos | None = None


@dataclass
class BinaryOp:
    op: str  # "+", "-", "*", "/", "^",
    #         "<", "<=", ">", ">=", "==", "!=", "&&", "||"
    left: Expr
    right: Expr
    pos: SourcePos | None = None


@dataclass
class FunctionCall:
    name: Identifier
    args: list[Expr]
    pos: SourcePos | None = None


# Discriminated union of expression-valued nodes.
Expr = NumberLit | Identifier | UnaryOp | BinaryOp | FunctionCall


# ---------------------------------------------------------------------------
# Declarations and statements
# ---------------------------------------------------------------------------


@dataclass
class VarDecl:
    kind: VarKind
    names: list[Identifier]
    pos: SourcePos | None = None


@dataclass
class VarexoDecl:
    names: list[Identifier]
    pos: SourcePos | None = None


@dataclass
class ParameterDecl:
    names: list[Identifier]
    pos: SourcePos | None = None


@dataclass
class ParameterValue:
    name: Identifier
    value: Expr
    pos: SourcePos | None = None


# Discriminated union of top-level statements. Will gain members
# (ModelBlock, InitvalBlock, ShocksBlock, …) as the grammar grows.
Statement = VarDecl | VarexoDecl | ParameterDecl | ParameterValue


@dataclass
class ModelFile:
    """Top-level AST node for a parsed .mod file."""

    statements: list[Statement] = field(default_factory=list)

"""AST node dataclasses for the dynare-ct parser.

Covers declarations (var / varexo / parameters), parameter-value
assignments, the expression sub-grammar (arithmetic, comparison,
logical, unary, function calls, dict literals, string literals), and
the model block (equations with optional tags). New node types land as
the grammar grows to encompass initval, shocks, etc.
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
class StringLit:
    value: str  # quotes stripped
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
class KeywordArg:
    """A single ``name=value`` pair inside a function-call argument list."""

    name: Identifier
    value: Expr
    pos: SourcePos | None = None


@dataclass
class FunctionCall:
    name: Identifier
    args: list[Expr] = field(default_factory=list)
    kwargs: list[KeywordArg] = field(default_factory=list)
    pos: SourcePos | None = None


@dataclass
class DictEntry:
    """A single ``key: value`` entry inside a dict literal."""

    key: Identifier
    value: Expr
    pos: SourcePos | None = None


@dataclass
class DictLiteral:
    entries: list[DictEntry] = field(default_factory=list)
    pos: SourcePos | None = None


# Discriminated union of expression-valued nodes.
Expr = NumberLit | StringLit | Identifier | UnaryOp | BinaryOp | FunctionCall | DictLiteral


# ---------------------------------------------------------------------------
# Equations and the model block
# ---------------------------------------------------------------------------


@dataclass
class Equation:
    """A single equation inside a model block.

    Two surface forms are accepted:

    - explicit ``LHS = RHS;``  → ``lhs`` is the LHS expression.
    - bare ``expr;``           → ``lhs is None``; the equation is ``expr == 0``.
    """

    lhs: Expr | None
    rhs: Expr
    tags: dict[str, str] = field(default_factory=dict)
    pos: SourcePos | None = None


@dataclass
class ModelBlock:
    equations: list[Equation] = field(default_factory=list)
    pos: SourcePos | None = None


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
# (InitvalBlock, ShocksBlock, …) as the grammar grows.
Statement = VarDecl | VarexoDecl | ParameterDecl | ParameterValue | ModelBlock


@dataclass
class ModelFile:
    """Top-level AST node for a parsed .mod file."""

    statements: list[Statement] = field(default_factory=list)

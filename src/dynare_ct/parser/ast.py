"""AST node dataclasses for the dynare-ct parser.

Step 1 covers declaration statements only. New node types land as the
grammar grows (expressions in step 2, the model block in step 3, …).
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


@dataclass
class Identifier:
    name: str
    pos: SourcePos | None = None


@dataclass
class NumberLit:
    value: float
    pos: SourcePos | None = None


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
    value: NumberLit
    pos: SourcePos | None = None


# Discriminated union of statements parsed at step 1. Will gain members
# (ModelBlock, InitvalBlock, ShocksBlock, …) as later steps extend the
# grammar.
Statement = VarDecl | VarexoDecl | ParameterDecl | ParameterValue


@dataclass
class ModelFile:
    """Top-level AST node for a parsed .mod file."""

    statements: list[Statement] = field(default_factory=list)

"""AST node dataclasses for the continuo parser.

Covers declarations (var / varexo / parameters), parameter-value
assignments, the expression sub-grammar (arithmetic, comparison,
logical, unary, function calls, dict literals, string literals), the
model block (equations with optional tags), the initval / initial_guess
blocks, the shocks block (with multi-revelation path assignments), the
steady_state_model block, and the simulate / steady commands.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class VarKind(Enum):
    """Endogenous variable classification: state, jump, or algebraic."""

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
# initval and initial_guess
# ---------------------------------------------------------------------------


@dataclass
class Assignment:
    """A single ``LHS = RHS;`` line inside ``initval`` or ``initial_guess``.

    The LHS is parsed as a generic expression. The IR layer validates
    that it is one of the allowed shapes (``Identifier`` or
    ``FunctionCall`` named ``diff(...)``) for the surrounding block.
    """

    lhs: Expr
    rhs: Expr
    pos: SourcePos | None = None


@dataclass
class InitvalBlock:
    """Initial values for state variables (the BVP's left boundary).

    ``steady=True`` flags use of the ``initval(steady)`` sugar — auto-fill
    every state from the initial steady state. ``kwargs`` carries any
    extra arguments to the qualifier (e.g. ``e={delta: 0.05}`` for
    anchoring at a hypothetical exogenous configuration).
    """

    steady: bool = False
    kwargs: list[KeywordArg] = field(default_factory=list)
    assignments: list[Assignment] = field(default_factory=list)
    pos: SourcePos | None = None


@dataclass
class InitialGuessBlock:
    """Optional starting iterate for the nonlinear solvers."""

    assignments: list[Assignment] = field(default_factory=list)
    pos: SourcePos | None = None


# ---------------------------------------------------------------------------
# Shocks
# ---------------------------------------------------------------------------


@dataclass
class PathAssignment:
    """A single ``path = …;`` or ``path at t=…  = …;`` line.

    ``reveal_time`` is the expression after ``t=``, or ``None`` for the
    default form (implicitly t=0). ``path`` is the expected-path
    expression.
    """

    reveal_time: Expr | None
    path: Expr
    pos: SourcePos | None = None


@dataclass
class ShockEntry:
    """One ``var <name>;`` followed by its path assignments.

    The IR validates that ``name`` corresponds to a declared ``varexo``
    and enforces the design's "no mixing of bare ``path = …`` with
    explicit ``path at t=0 = …`` for the same shock" rule.
    """

    name: Identifier
    paths: list[PathAssignment] = field(default_factory=list)
    pos: SourcePos | None = None


@dataclass
class ShocksBlock:
    entries: list[ShockEntry] = field(default_factory=list)
    pos: SourcePos | None = None


# ---------------------------------------------------------------------------
# Analytical steady state
# ---------------------------------------------------------------------------


@dataclass
class SteadyStateModelBlock:
    """Analytical steady state defined as ``x_ss = h(θ, e)``.

    The IR layer enforces:
      - LHS of every assignment is a declared endogenous variable
        (``var``, of any subtype) — never a ``varexo`` or ``parameter``;
      - when the block is present it must be complete (cover every
        endogenous variable) for v1.
    """

    assignments: list[Assignment] = field(default_factory=list)
    pos: SourcePos | None = None


# ---------------------------------------------------------------------------
# Commands: simulate / steady
# ---------------------------------------------------------------------------


@dataclass
class SimulateCommand:
    """Run the perfect-foresight solver.

    The grammar accepts any positional / keyword arguments; the IR
    layer enforces that ``T`` and ``N`` are present (mandatory),
    ``scheme`` is one of the supported discretisation schemes, and no
    unknown keys appear.
    """

    args: list[Expr] = field(default_factory=list)
    kwargs: list[KeywordArg] = field(default_factory=list)
    pos: SourcePos | None = None


@dataclass
class SteadyCommand:
    """Compute and report a steady state for inspection / diagnostics.

    Bare ``steady;`` defaults to ``t = T`` under the final information
    set. The optional argument list may carry ``t=…`` (which point on
    the simulated horizon) and / or ``e={…}`` (an explicit exogenous
    configuration) — see /Steady state and initial conditions/ in the
    design document. Validation lives in the IR.
    """

    args: list[Expr] = field(default_factory=list)
    kwargs: list[KeywordArg] = field(default_factory=list)
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


# Discriminated union of top-level statements.
Statement = (
    VarDecl
    | VarexoDecl
    | ParameterDecl
    | ParameterValue
    | ModelBlock
    | InitvalBlock
    | InitialGuessBlock
    | ShocksBlock
    | SteadyStateModelBlock
    | SimulateCommand
    | SteadyCommand
)


@dataclass
class ModelFile:
    """Top-level AST node for a parsed .mod file."""

    statements: list[Statement] = field(default_factory=list)

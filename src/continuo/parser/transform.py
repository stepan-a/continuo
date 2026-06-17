"""Lark Transformer: lifts the parse tree into typed AST dataclasses."""

from __future__ import annotations

from dataclasses import dataclass

from lark import Token, Transformer, v_args

from continuo.parser.ast import (
    Assignment,
    BinaryOp,
    DictEntry,
    DictLiteral,
    Equation,
    Expr,
    FunctionCall,
    Identifier,
    InitialGuessBlock,
    InitvalBlock,
    KeywordArg,
    ModelBlock,
    ModelFile,
    NumberLit,
    ParameterDecl,
    ParameterValue,
    PathAssignment,
    ShockEntry,
    ShocksBlock,
    SimulateCommand,
    SourcePos,
    Statement,
    SteadyCommand,
    SteadyStateModelBlock,
    StringLit,
    UnaryOp,
    VarDecl,
    VarexoDecl,
    VarKind,
)


def _pos(tok: Token) -> SourcePos:
    return SourcePos(line=tok.line, column=tok.column)


def _strip_quotes(raw: str) -> str:
    """Remove the surrounding quote characters from a STRING token's text."""
    return raw[1:-1]


@dataclass
class _QualFlag:
    """A bare-word item inside a ``var`` qualifier (state/jump/positive/...)."""

    name: str
    token: Token


@dataclass
class _QualBounds:
    """A ``boundaries=(lo, hi)`` item; a ``None`` side denotes an open bound."""

    lower: Expr | None
    upper: Expr | None


_QualItem = _QualFlag | _QualBounds


@v_args(inline=True)
class ASTBuilder(Transformer):
    # --- top level ------------------------------------------------------

    def start(self, *statements: Statement) -> ModelFile:
        return ModelFile(statements=list(statements))

    # --- declarations ---------------------------------------------------

    def var_decl_qualified(self, qualifier: list[_QualItem], names: list[Identifier]) -> VarDecl:
        kind, constraint = self._resolve_qualifier(qualifier)
        return VarDecl(kind=kind, names=names, constraint=constraint)

    def var_decl_unqualified(self, names: list[Identifier]) -> VarDecl:
        return VarDecl(kind=VarKind.ALGEBRAIC, names=names)

    def var_qualifier(self, *items: _QualItem) -> list[_QualItem]:
        return list(items)

    def qual_flag(self, ident_token: Token) -> _QualFlag:
        return _QualFlag(name=ident_token.value, token=ident_token)

    def qual_boundaries(self, lower: Expr | None, upper: Expr | None) -> _QualBounds:
        return _QualBounds(lower=lower, upper=upper)

    def bound_inf(self) -> None:
        return None

    def bound_neg_inf(self) -> None:
        return None

    def bound_expr(self, expr: Expr) -> Expr:
        return expr

    def _resolve_qualifier(
        self, items: list[_QualItem]
    ) -> tuple[VarKind, tuple[Expr | None, Expr | None] | None]:
        """Split a qualifier list into a single type and a single constraint."""
        kind: VarKind | None = None
        constraint: tuple[Expr | None, Expr | None] | None = None
        for item in items:
            if isinstance(item, _QualFlag):
                name = item.name
                if name in ("state", "jump"):
                    if kind is not None:
                        raise SyntaxError(
                            f"conflicting var type {name!r} at line {item.token.line}, "
                            f"column {item.token.column}; a var has at most one of "
                            "'state' / 'jump'"
                        )
                    kind = VarKind.STATE if name == "state" else VarKind.JUMP
                elif name in ("positive", "negative"):
                    constraint = self._set_constraint(
                        constraint,
                        (NumberLit(0.0), None) if name == "positive" else (None, NumberLit(0.0)),
                        item.token,
                    )
                else:
                    raise SyntaxError(
                        f"unknown var qualifier {name!r} at line {item.token.line}, "
                        f"column {item.token.column}; expected 'state', 'jump', "
                        "'positive', 'negative' or 'boundaries=(lo, hi)'"
                    )
            else:  # _QualBounds
                constraint = self._set_constraint(constraint, (item.lower, item.upper), None)
        return (kind if kind is not None else VarKind.ALGEBRAIC, constraint)

    @staticmethod
    def _set_constraint(
        existing: tuple[Expr | None, Expr | None] | None,
        new: tuple[Expr | None, Expr | None],
        token: Token | None,
    ) -> tuple[Expr | None, Expr | None]:
        if existing is not None:
            where = f" at line {token.line}, column {token.column}" if token is not None else ""
            raise SyntaxError(
                f"more than one domain constraint in a var qualifier{where}; a var "
                "has at most one of 'positive' / 'negative' / 'boundaries=(lo, hi)'"
            )
        return new

    def varexo_decl(self, names: list[Identifier]) -> VarexoDecl:
        return VarexoDecl(names=names)

    def parameters_decl(self, names: list[Identifier]) -> ParameterDecl:
        return ParameterDecl(names=names)

    def param_value(self, name_token: Token, value_expr: Expr) -> ParameterValue:
        return ParameterValue(
            name=Identifier(name=name_token.value, pos=_pos(name_token)),
            value=value_expr,
        )

    # --- lists ----------------------------------------------------------

    def ident_list(self, *tokens: Token) -> list[Identifier]:
        return [Identifier(name=t.value, pos=_pos(t)) for t in tokens]

    # --- model block ----------------------------------------------------

    def model_block(self, *equations: Equation) -> ModelBlock:
        return ModelBlock(equations=list(equations))

    def equation_with_tags(self, tags: dict[str, str], equation: Equation) -> Equation:
        equation.tags = tags
        return equation

    def equation_without_tags(self, equation: Equation) -> Equation:
        return equation

    def equation_eq(self, lhs: Expr, rhs: Expr) -> Equation:
        return Equation(lhs=lhs, rhs=rhs)

    def equation_zero(self, expr: Expr) -> Equation:
        return Equation(lhs=None, rhs=expr)

    def tags(self, *pairs: tuple[str, str]) -> dict[str, str]:
        return dict(pairs)

    def tag(self, name_token: Token, value_token: Token) -> tuple[str, str]:
        return (name_token.value, _strip_quotes(value_token.value))

    # --- initval and initial_guess -------------------------------------

    def initval_plain(self, *assignments: Assignment) -> InitvalBlock:
        return InitvalBlock(steady=False, kwargs=[], assignments=list(assignments))

    def initval_steady(self, *assignments: Assignment) -> InitvalBlock:
        return InitvalBlock(steady=True, kwargs=[], assignments=list(assignments))

    def initval_steady_kwargs(self, *items: KeywordArg | Assignment) -> InitvalBlock:
        # Children come through in source order: kwargs first (from the
        # qualifier), then any number of assignments. Splitting by type
        # is robust to grammar refactors.
        kwargs: list[KeywordArg] = []
        assignments: list[Assignment] = []
        for item in items:
            if isinstance(item, KeywordArg):
                kwargs.append(item)
            else:
                assignments.append(item)
        return InitvalBlock(steady=True, kwargs=kwargs, assignments=assignments)

    def initial_guess_block(self, *assignments: Assignment) -> InitialGuessBlock:
        return InitialGuessBlock(assignments=list(assignments))

    def assignment(self, lhs: Expr, rhs: Expr) -> Assignment:
        return Assignment(lhs=lhs, rhs=rhs)

    # --- shocks block --------------------------------------------------

    def shocks_block(self, *entries: ShockEntry) -> ShocksBlock:
        return ShocksBlock(entries=list(entries))

    def shock_entry(self, name_token: Token, *paths: PathAssignment) -> ShockEntry:
        return ShockEntry(
            name=Identifier(name=name_token.value, pos=_pos(name_token)),
            paths=list(paths),
        )

    def path_default(self, path_expr: Expr) -> PathAssignment:
        return PathAssignment(reveal_time=None, path=path_expr)

    def path_at_explicit(
        self, time_var_token: Token, reveal_time: Expr, path_expr: Expr
    ) -> PathAssignment:
        # The grammar accepts any IDENT after `path at`; we require it to
        # be the reserved continuous-time variable `t`.
        if time_var_token.value != "t":
            raise SyntaxError(
                f"expected 't' after 'path at' at line {time_var_token.line}, "
                f"column {time_var_token.column}; got {time_var_token.value!r}"
            )
        return PathAssignment(reveal_time=reveal_time, path=path_expr)

    # --- steady_state_model block --------------------------------------

    def steady_state_model_block(self, *assignments: Assignment) -> SteadyStateModelBlock:
        return SteadyStateModelBlock(assignments=list(assignments))

    # --- commands ------------------------------------------------------

    def simulate_command(self, args_split: tuple[list[Expr], list[KeywordArg]]) -> SimulateCommand:
        positional, keywords = args_split
        return SimulateCommand(args=positional, kwargs=keywords)

    def steady_bare(self) -> SteadyCommand:
        return SteadyCommand(args=[], kwargs=[])

    def steady_with_args(self, args_split: tuple[list[Expr], list[KeywordArg]]) -> SteadyCommand:
        positional, keywords = args_split
        return SteadyCommand(args=positional, kwargs=keywords)

    # --- expressions: atoms --------------------------------------------

    def number_atom(self, num_token: Token) -> NumberLit:
        return NumberLit(value=float(num_token.value), pos=_pos(num_token))

    def string_atom(self, str_token: Token) -> StringLit:
        return StringLit(value=_strip_quotes(str_token.value), pos=_pos(str_token))

    def ident_atom(self, ident_token: Token) -> Identifier:
        return Identifier(name=ident_token.value, pos=_pos(ident_token))

    # --- expressions: dict literals ------------------------------------

    def dict_empty(self) -> DictLiteral:
        return DictLiteral(entries=[])

    def dict_nonempty(self, entries: list[DictEntry]) -> DictLiteral:
        return DictLiteral(entries=entries)

    def dict_entries(self, *entries: DictEntry) -> list[DictEntry]:
        return list(entries)

    def dict_entry(self, key_token: Token, value_expr: Expr) -> DictEntry:
        return DictEntry(
            key=Identifier(name=key_token.value, pos=_pos(key_token)),
            value=value_expr,
        )

    # --- expressions: function calls + arg list ------------------------

    def func_call_no_args(self, name_token: Token) -> FunctionCall:
        return FunctionCall(
            name=Identifier(name=name_token.value, pos=_pos(name_token)),
            args=[],
            kwargs=[],
        )

    def func_call_with_args(
        self,
        name_token: Token,
        args_split: tuple[list[Expr], list[KeywordArg]],
    ) -> FunctionCall:
        positional, keywords = args_split
        return FunctionCall(
            name=Identifier(name=name_token.value, pos=_pos(name_token)),
            args=positional,
            kwargs=keywords,
        )

    def arg_list(self, *items: Expr | KeywordArg) -> tuple[list[Expr], list[KeywordArg]]:
        positional: list[Expr] = []
        keywords: list[KeywordArg] = []
        for item in items:
            if isinstance(item, KeywordArg):
                keywords.append(item)
            else:
                positional.append(item)
        return (positional, keywords)

    def kwarg(self, name_token: Token, value_expr: Expr) -> KeywordArg:
        return KeywordArg(
            name=Identifier(name=name_token.value, pos=_pos(name_token)),
            value=value_expr,
        )

    # --- expressions: unary --------------------------------------------

    def neg_op(self, operand: Expr) -> UnaryOp:
        return UnaryOp(op="-", operand=operand)

    def not_op(self, operand: Expr) -> UnaryOp:
        return UnaryOp(op="!", operand=operand)

    # --- expressions: binary -------------------------------------------

    def or_op(self, left: Expr, right: Expr) -> BinaryOp:
        return BinaryOp(op="||", left=left, right=right)

    def and_op(self, left: Expr, right: Expr) -> BinaryOp:
        return BinaryOp(op="&&", left=left, right=right)

    def cmp_op(self, left: Expr, op_token: Token, right: Expr) -> BinaryOp:
        return BinaryOp(op=op_token.value, left=left, right=right)

    def add_op(self, left: Expr, op_token: Token, right: Expr) -> BinaryOp:
        return BinaryOp(op=op_token.value, left=left, right=right)

    def mul_op(self, left: Expr, op_token: Token, right: Expr) -> BinaryOp:
        return BinaryOp(op=op_token.value, left=left, right=right)

    def pow_op(self, left: Expr, right: Expr) -> BinaryOp:
        return BinaryOp(op="^", left=left, right=right)

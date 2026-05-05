"""Lark Transformer: lifts the parse tree into typed AST dataclasses."""

from __future__ import annotations

from lark import Token, Transformer, v_args

from dynare_ct.parser.ast import (
    BinaryOp,
    DictEntry,
    DictLiteral,
    Equation,
    Expr,
    FunctionCall,
    Identifier,
    KeywordArg,
    ModelBlock,
    ModelFile,
    NumberLit,
    ParameterDecl,
    ParameterValue,
    SourcePos,
    Statement,
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


@v_args(inline=True)
class ASTBuilder(Transformer):
    # --- top level ------------------------------------------------------

    def start(self, *statements: Statement) -> ModelFile:
        return ModelFile(statements=list(statements))

    # --- declarations ---------------------------------------------------

    def var_decl_qualified(self, qualifier: VarKind, names: list[Identifier]) -> VarDecl:
        return VarDecl(kind=qualifier, names=names)

    def var_decl_unqualified(self, names: list[Identifier]) -> VarDecl:
        return VarDecl(kind=VarKind.ALGEBRAIC, names=names)

    def var_qualifier(self, ident_token: Token) -> VarKind:
        name = ident_token.value
        if name == "state":
            return VarKind.STATE
        if name == "jump":
            return VarKind.JUMP
        raise SyntaxError(
            f"unknown var qualifier {name!r} at line {ident_token.line}, "
            f"column {ident_token.column}; expected 'state' or 'jump'"
        )

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

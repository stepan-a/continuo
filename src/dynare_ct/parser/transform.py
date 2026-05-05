"""Lark Transformer: lifts the parse tree into typed AST dataclasses."""

from __future__ import annotations

from lark import Token, Transformer, v_args

from dynare_ct.parser.ast import (
    BinaryOp,
    Expr,
    FunctionCall,
    Identifier,
    ModelFile,
    NumberLit,
    ParameterDecl,
    ParameterValue,
    SourcePos,
    Statement,
    UnaryOp,
    VarDecl,
    VarexoDecl,
    VarKind,
)


def _pos(tok: Token) -> SourcePos:
    return SourcePos(line=tok.line, column=tok.column)


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

    # --- expressions: atoms --------------------------------------------

    def number_atom(self, num_token: Token) -> NumberLit:
        return NumberLit(value=float(num_token.value), pos=_pos(num_token))

    def ident_atom(self, ident_token: Token) -> Identifier:
        return Identifier(name=ident_token.value, pos=_pos(ident_token))

    def func_call_no_args(self, name_token: Token) -> FunctionCall:
        return FunctionCall(
            name=Identifier(name=name_token.value, pos=_pos(name_token)),
            args=[],
        )

    def func_call_with_args(self, name_token: Token, args: list[Expr]) -> FunctionCall:
        return FunctionCall(
            name=Identifier(name=name_token.value, pos=_pos(name_token)),
            args=args,
        )

    def arg_list(self, *exprs: Expr) -> list[Expr]:
        return list(exprs)

    # --- expressions: unary --------------------------------------------

    def neg_op(self, operand: Expr) -> UnaryOp:
        return UnaryOp(op="-", operand=operand)

    def not_op(self, operand: Expr) -> UnaryOp:
        return UnaryOp(op="!", operand=operand)

    # --- expressions: binary -------------------------------------------
    # `||` and `&&` use string literals in the grammar (filtered out of
    # the children list); the operator name is implied by the method name.
    # `^` likewise.
    # `+ -`, `* /`, and the comparison operators come through as explicit
    # tokens (ADD_OP, MUL_OP, CMP_OP) so the same method handles all
    # variants in each precedence class.

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

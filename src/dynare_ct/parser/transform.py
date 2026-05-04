"""Lark Transformer: lifts the parse tree into typed AST dataclasses."""

from __future__ import annotations

from lark import Token, Transformer, v_args

from dynare_ct.parser.ast import (
    Identifier,
    ModelFile,
    NumberLit,
    ParameterDecl,
    ParameterValue,
    SourcePos,
    Statement,
    VarDecl,
    VarexoDecl,
    VarKind,
)


def _pos(tok: Token) -> SourcePos:
    return SourcePos(line=tok.line, column=tok.column)


@v_args(inline=True)
class ASTBuilder(Transformer):
    # --- top level ----------------------------------------------------

    def start(self, *statements: Statement) -> ModelFile:
        return ModelFile(statements=list(statements))

    # --- declarations -------------------------------------------------

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

    def param_value(self, name_token: Token, value_token: Token) -> ParameterValue:
        return ParameterValue(
            name=Identifier(name=name_token.value, pos=_pos(name_token)),
            value=NumberLit(value=float(value_token.value), pos=_pos(value_token)),
        )

    # --- lists --------------------------------------------------------

    def ident_list(self, *tokens: Token) -> list[Identifier]:
        return [Identifier(name=t.value, pos=_pos(t)) for t in tokens]

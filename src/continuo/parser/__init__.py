"""Lark-based parser for the continuo .mod language.

Public API: :func:`parse` — turn a source string into a typed AST.
"""

from __future__ import annotations

from pathlib import Path

from lark import Lark
from lark.exceptions import VisitError

from continuo.parser.ast import ModelFile
from continuo.parser.transform import ASTBuilder

__all__ = ["parse"]


_GRAMMAR_PATH = Path(__file__).parent / "grammar.lark"
_PARSER: Lark | None = None


def _get_parser() -> Lark:
    global _PARSER
    if _PARSER is None:
        _PARSER = Lark.open(
            str(_GRAMMAR_PATH),
            parser="lalr",
            propagate_positions=True,
        )
    return _PARSER


def parse(text: str) -> ModelFile:
    """Parse a .mod file source string into a typed AST."""
    tree = _get_parser().parse(text)
    try:
        return ASTBuilder().transform(tree)
    except VisitError as e:
        # Surface the underlying error from a Transformer method
        # rather than Lark's wrapper; keeps caller-side `except` clean.
        raise e.orig_exc from None

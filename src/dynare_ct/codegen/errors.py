"""Codegen error type.

Raised when a (semantically valid) model expression cannot be lowered to a
CasADi expression — an unknown function, a construct with no numeric
meaning (a string or dict literal in an equation), or a missing symbol.
By the time codegen runs the IR has validated the model, so these are
mostly guards against constructs the model language allows syntactically
but the numeric layer does not.
"""

from __future__ import annotations

from dynare_ct.parser.ast import SourcePos

__all__ = ["CodegenError"]


class CodegenError(Exception):
    """A lowering error, optionally carrying a source position."""

    def __init__(self, message: str, pos: SourcePos | None = None):
        self.message = message
        self.pos = pos
        super().__init__(self._render())

    def _render(self) -> str:
        if self.pos is not None:
            return f"{self.pos.line}:{self.pos.column}: {self.message}"
        return self.message

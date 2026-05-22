"""IR semantic error type.

Construction of the :class:`~dynare_ct.ir.model.Model` from the AST is the
single place where semantic errors are raised — undeclared names, class
inconsistencies, incomplete boundary data, and so on. These are distinct
from the syntactic errors the parser raises: a :class:`IRError` always
refers to a well-formed parse that does not describe a valid model.
"""

from __future__ import annotations

from dynare_ct.parser.ast import SourcePos

__all__ = ["IRError"]


class IRError(Exception):
    """A semantic error, optionally carrying a source position.

    ``pos`` refers to the post-macroexpansion source; callers holding the
    macro line map format it back to the user's original file.
    """

    def __init__(self, message: str, pos: SourcePos | None = None):
        self.message = message
        self.pos = pos
        super().__init__(self._render())

    def _render(self) -> str:
        if self.pos is not None:
            return f"{self.pos.line}:{self.pos.column}: {self.message}"
        return self.message

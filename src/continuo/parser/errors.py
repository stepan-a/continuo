"""Parser error types.

Re-exports Lark's native exceptions so callers have a single place to
import from. Domain-specific wrappers (with positions threaded through
the macro line-map) will be added when the macro layer lands.
"""

from lark.exceptions import (
    LarkError,
    UnexpectedCharacters,
    UnexpectedInput,
    UnexpectedToken,
)

__all__ = [
    "LarkError",
    "UnexpectedCharacters",
    "UnexpectedInput",
    "UnexpectedToken",
]

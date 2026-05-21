"""Line-oriented lexer for macro directives.

The macro language is line-based: a line is a directive when its first
non-blank characters are ``@#``; everything else is verbatim text (which
may still contain inline ``@{...}`` expansions, resolved later by the
driver). This module only classifies and splits -- it attaches no
meaning to directives and raises no semantic errors. Validation of
directive arguments and block balancing happens in :mod:`.expand`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["TextLine", "Directive", "Line", "lex"]

# Keyword followed by either whitespace+rest or end-of-line.
_DIRECTIVE_RE = re.compile(r"@#\s*([A-Za-z]+)\b[ \t]*(.*)$")


@dataclass(frozen=True)
class TextLine:
    """A verbatim line of model text (may contain ``@{...}``)."""

    text: str
    lineno: int


@dataclass(frozen=True)
class Directive:
    """A ``@#`` directive: its keyword and the raw remainder of the line."""

    keyword: str  # 'define', 'if', 'for', 'include', ...
    args: str  # everything after the keyword, stripped of trailing space
    lineno: int


Line = TextLine | Directive


def lex(text: str) -> list[Line]:
    """Classify each line of ``text`` as a :class:`Directive` or :class:`TextLine`.

    Line numbers are 1-indexed and refer to ``text`` as given.
    """
    lines: list[Line] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.lstrip()
        if stripped.startswith("@#"):
            m = _DIRECTIVE_RE.match(stripped)
            if m is None:
                # "@#" with no keyword; leave keyword empty for the driver
                # to reject with a position.
                lines.append(Directive(keyword="", args=stripped[2:].strip(), lineno=lineno))
            else:
                lines.append(Directive(keyword=m.group(1), args=m.group(2).rstrip(), lineno=lineno))
        else:
            lines.append(TextLine(text=raw, lineno=lineno))
    return lines

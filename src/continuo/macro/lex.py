"""Line-oriented lexer for macro directives.

The macro language is line-based: a line is a directive when its first
non-blank characters are ``@#``; everything else is verbatim text (which
may still contain inline ``@{...}`` expansions, resolved later by the
driver). This module only classifies and splits -- it attaches no
meaning to directives and raises no semantic errors. Validation of
directive arguments and block balancing happens in :mod:`.expand`.

Two lexical conveniences apply to directive lines (not to model text,
whose comments the parser handles): a trailing backslash continues the
directive on the next physical line, and ``//`` outside a string literal
starts an end-of-line comment.
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

    Line numbers are 1-indexed and refer to ``text`` as given; a directive
    spanning continuation lines is reported at its first physical line.
    """
    physical = text.splitlines()
    lines: list[Line] = []
    i = 0
    while i < len(physical):
        raw = physical[i]
        lineno = i + 1
        if not raw.lstrip().startswith("@#"):
            lines.append(TextLine(text=raw, lineno=lineno))
            i += 1
            continue
        # Join backslash-continued physical lines into one logical directive.
        content = raw
        while content.rstrip().endswith("\\") and i + 1 < len(physical):
            content = content.rstrip()[:-1] + " " + physical[i + 1]
            i += 1
        lines.append(_directive(_strip_comment(content.lstrip()), lineno))
        i += 1
    return lines


def _directive(stripped: str, lineno: int) -> Directive:
    m = _DIRECTIVE_RE.match(stripped)
    if m is None:
        # "@#" with no keyword; leave keyword empty for the driver to reject.
        return Directive(keyword="", args=stripped[2:].strip(), lineno=lineno)
    return Directive(keyword=m.group(1), args=m.group(2).rstrip(), lineno=lineno)


def _strip_comment(s: str) -> str:
    """Drop a ``//`` end-of-line comment, ignoring ``//`` inside strings."""
    quote = ""
    for i, c in enumerate(s):
        if quote:
            if c == quote:
                quote = ""
        elif c in "\"'":
            quote = c
        elif c == "/" and i + 1 < len(s) and s[i + 1] == "/":
            return s[:i].rstrip()
    return s

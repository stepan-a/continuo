"""Back-pointer datastructure mapping expanded text to original source.

Macro expansion produces a flat block of text whose line numbering bears
no relation to the files the user wrote. The :class:`LineMap` records, for
every line of expanded output, where it came from: the source file, the
line within that file, and the stack of expansion frames (``@#for``
iterations, ``@#include`` sites) active when it was emitted.

Downstream layers (parser, IR) report errors against expanded-text line
numbers; :meth:`LineMap.format_location` turns such a number back into a
message phrased in terms of the user's own source.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Frame:
    """One level of expansion context.

    ``directive`` is the directive that introduced the frame (e.g.
    ``'@#for c in countries'`` or ``'@#include'``); ``detail`` qualifies
    it (e.g. ``'iteration EU'`` or ``'at line 12 of main.mod'``).
    """

    directive: str
    detail: str

    def __str__(self) -> str:
        return f"{self.directive} ({self.detail})" if self.detail else self.directive


@dataclass(frozen=True)
class Origin:
    """Where one line of expanded output came from.

    ``context`` is ordered outermost-first (the include nearest the entry
    point comes first, the innermost loop iteration last).
    """

    file: str
    line: int
    context: tuple[Frame, ...] = ()


class LineMap:
    """Maps 1-indexed expanded-output line numbers to their :class:`Origin`."""

    def __init__(self) -> None:
        self._origins: list[Origin] = []

    def append(self, origin: Origin) -> None:
        """Record the origin of the next expanded output line."""
        self._origins.append(origin)

    def __len__(self) -> int:
        return len(self._origins)

    def origin(self, expanded_line: int) -> Origin:
        """Return the :class:`Origin` of a 1-indexed expanded line."""
        if not 1 <= expanded_line <= len(self._origins):
            raise IndexError(
                f"expanded line {expanded_line} out of range (1..{len(self._origins)})"
            )
        return self._origins[expanded_line - 1]

    def format_location(self, expanded_line: int) -> str:
        """Render a human-friendly description of an expanded line's origin.

        Frames are listed innermost-first, mirroring how a reader traces an
        error outward from the equation back to the entry-point file.
        """
        origin = self.origin(expanded_line)
        msg = f"{origin.file} line {origin.line}"
        if origin.context:
            trail = ", ".join(str(f) for f in reversed(origin.context))
            msg += f", expanded from {trail}"
        return msg

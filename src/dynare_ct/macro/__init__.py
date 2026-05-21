"""Macroprocessor: text-in, text-out expansion of @# directives.

Runs before the parser, expanding Dynare-compatible directives
(``@#define``, ``@#if`` / ``@#elseif`` / ``@#else`` / ``@#endif``,
``@#ifdef`` / ``@#ifndef``, ``@#for`` / ``@#endfor``, ``@#include``) and
inline ``@{expression}`` substitutions. The model grammar is never seen
here; this layer transforms text only.

Public API::

    expanded_text, linemap = macro.expand("model.mod")
    expanded_text, linemap = macro.expand_string(source)
"""

from __future__ import annotations

from dynare_ct.macro.eval import MacroError
from dynare_ct.macro.expand import expand, expand_string
from dynare_ct.macro.linemap import Frame, LineMap, Origin

__all__ = ["expand", "expand_string", "MacroError", "LineMap", "Origin", "Frame"]

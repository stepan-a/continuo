"""Expansion driver: directive stream in, expanded text + line map out.

Two passes. First the flat directive/text stream from :mod:`.lex` is
parsed into a block tree (``@#if`` and ``@#for`` nest a body). Then the
tree is walked against a macro environment, emitting verbatim text --
with inline ``@{...}`` expansions resolved -- and recording each output
line's origin in a :class:`~dynare_ct.macro.linemap.LineMap`.

The parser and IR layers downstream are unaware this pass ever ran; they
receive plain text plus the line map for error reporting.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from dynare_ct.macro.eval import MacroError, evaluate, is_truthy, value_to_text
from dynare_ct.macro.lex import Directive, TextLine, lex
from dynare_ct.macro.linemap import Frame, LineMap, Origin

__all__ = ["expand", "expand_string", "MacroError"]

_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_FOR_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s+in\s+(.+)", re.DOTALL)

# Directive keywords that terminate a block body (consumed by the opener).
_TERMINATORS = ("elseif", "else", "endif", "endfor")


# ---------------------------------------------------------------------------
# Block tree
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Text:
    text: str
    lineno: int


@dataclass(frozen=True)
class _Define:
    name: str
    expr: str
    lineno: int


@dataclass(frozen=True)
class _Include:
    arg: str
    lineno: int


@dataclass(frozen=True)
class _If:
    # Each branch is (condition, body); condition is None for @#else,
    # ("expr", text) for @#if/@#elseif, or ("ifdef"|"ifndef", name).
    branches: list[tuple[tuple[str, str] | None, list]]
    lineno: int


@dataclass(frozen=True)
class _For:
    var: str
    iter_expr: str
    body: list
    lineno: int


class _BlockParser:
    """Turns the flat line stream into a block tree."""

    def __init__(self, lines: list, file: str):
        self._lines = lines
        self._i = 0
        self._file = file

    def parse(self) -> list:
        body, term = self._body(terminators=())
        if term is not None:  # pragma: no cover - unreachable with empty terminators
            raise MacroError(f"unexpected @#{term.keyword}", file=self._file, line=term.lineno)
        return body

    def _body(self, terminators: tuple[str, ...]) -> tuple[list, Directive | None]:
        body: list = []
        while self._i < len(self._lines):
            line = self._lines[self._i]
            if isinstance(line, Directive) and line.keyword in terminators:
                return body, line  # leave terminator for the caller to consume
            self._i += 1
            if isinstance(line, TextLine):
                body.append(_Text(line.text, line.lineno))
            else:
                body.append(self._directive(line))
        return body, None

    def _directive(self, d: Directive):
        kw = d.keyword
        if kw == "define":
            return self._define(d)
        if kw == "include":
            if not d.args:
                self._fail("@#include requires a file path", d)
            return _Include(d.args, d.lineno)
        if kw in ("if", "ifdef", "ifndef"):
            return self._if(d)
        if kw == "for":
            return self._for(d)
        if kw == "":
            self._fail("missing directive keyword after '@#'", d)
        if kw in _TERMINATORS:
            self._fail(f"@#{kw} without a matching opener", d)
        self._fail(f"unsupported directive @#{kw}", d)

    def _define(self, d: Directive) -> _Define:
        name, sep, expr = d.args.partition("=")
        name = name.strip()
        if not sep or not _IDENT_RE.fullmatch(name) or not expr.strip():
            self._fail("malformed @#define; expected '@#define NAME = EXPRESSION'", d)
        return _Define(name, expr.strip(), d.lineno)

    def _if(self, d: Directive) -> _If:
        branches: list[tuple[tuple[str, str] | None, list]] = []
        cond = self._condition(d)
        while True:
            body, term = self._body(_TERMINATORS)
            if term is None or term.keyword == "endfor":
                self._fail("unterminated @#if (missing @#endif)", d)
            branches.append((cond, body))
            self._i += 1  # consume the terminator
            if term.keyword == "endif":
                break
            if term.keyword == "elseif":
                if not term.args:
                    self._fail("@#elseif requires a condition", term)
                cond = ("expr", term.args)
                continue
            # term.keyword == "else"
            else_body, end = self._body(("endif", "endfor"))
            if end is None or end.keyword != "endif":
                self._fail("unterminated @#if (missing @#endif after @#else)", d)
            branches.append((None, else_body))
            self._i += 1  # consume @#endif
            break
        return _If(branches, d.lineno)

    def _condition(self, d: Directive) -> tuple[str, str]:
        if d.keyword == "if":
            if not d.args:
                self._fail("@#if requires a condition", d)
            return ("expr", d.args)
        name = d.args.strip()  # ifdef / ifndef
        if not _IDENT_RE.fullmatch(name):
            self._fail(f"@#{d.keyword} requires a macro variable name", d)
        return (d.keyword, name)

    def _for(self, d: Directive) -> _For:
        m = _FOR_RE.fullmatch(d.args.strip())
        if m is None:
            self._fail("malformed @#for; expected '@#for VAR in EXPRESSION'", d)
        body, term = self._body(("endfor", "endif", "else", "elseif"))
        if term is None or term.keyword != "endfor":
            self._fail("unterminated @#for (missing @#endfor)", d)
        self._i += 1  # consume @#endfor
        return _For(m.group(1), m.group(2).strip(), body, d.lineno)

    def _fail(self, message: str, d: Directive):
        raise MacroError(message, file=self._file, line=d.lineno)


# ---------------------------------------------------------------------------
# Evaluation driver
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Ctx:
    """Per-file evaluation context threaded through the walk.

    ``env`` is shared (mutated in place by ``@#define`` and ``@#for``);
    ``file``, ``base_dir`` and ``context`` are replaced when descending
    into an ``@#include`` or an ``@#for`` iteration.
    """

    env: dict
    file: str
    base_dir: Path
    context: tuple[Frame, ...]


class _Expander:
    def __init__(self) -> None:
        self.out: list[str] = []
        self.linemap = LineMap()
        self.include_stack: list[Path] = []

    def run(self, text: str, ctx: _Ctx) -> None:
        self._run(_BlockParser(lex(text), ctx.file).parse(), ctx)

    def _run(self, body: list, ctx: _Ctx) -> None:
        for node in body:
            if isinstance(node, _Text):
                self._emit(self._subst(node.text, ctx, node.lineno), ctx, node.lineno)
            elif isinstance(node, _Define):
                ctx.env[node.name] = self._eval(node.expr, ctx, node.lineno)
            elif isinstance(node, _If):
                for cond, branch in node.branches:
                    if self._cond_true(cond, ctx, node.lineno):
                        self._run(branch, ctx)
                        break
            elif isinstance(node, _For):
                self._run_for(node, ctx)
            elif isinstance(node, _Include):
                self._include(node, ctx)

    def _run_for(self, node: _For, ctx: _Ctx) -> None:
        items = self._eval(node.iter_expr, ctx, node.lineno)
        if not isinstance(items, list):
            raise MacroError("@#for can only iterate over a list", file=ctx.file, line=node.lineno)
        directive = f"@#for {node.var} in {node.iter_expr}"
        for item in items:
            ctx.env[node.var] = item
            frame = Frame(directive, f"iteration {value_to_text(item)}")
            self._run(node.body, replace(ctx, context=ctx.context + (frame,)))

    def _include(self, node: _Include, ctx: _Ctx) -> None:
        raw = self._subst(node.arg, ctx, node.lineno).strip()
        path_str = raw[1:-1] if len(raw) >= 2 and raw[0] in "\"'" and raw[-1] == raw[0] else raw
        target = ctx.base_dir / path_str
        resolved = target.resolve()
        if resolved in self.include_stack:
            raise MacroError(f"circular @#include of {path_str!r}", file=ctx.file, line=node.lineno)
        if not target.is_file():
            raise MacroError(
                f"@#include file not found: {path_str!r}", file=ctx.file, line=node.lineno
            )
        frame = Frame("@#include", f"at line {node.lineno} of {Path(ctx.file).name}")
        self.include_stack.append(resolved)
        self.run(
            target.read_text(),
            _Ctx(ctx.env, str(target), target.parent, ctx.context + (frame,)),
        )
        self.include_stack.pop()

    def _emit(self, text: str, ctx: _Ctx, lineno: int) -> None:
        self.out.append(text)
        self.linemap.append(Origin(ctx.file, lineno, ctx.context))

    def _cond_true(self, cond: tuple[str, str] | None, ctx: _Ctx, lineno: int) -> bool:
        if cond is None:  # @#else
            return True
        kind, payload = cond
        if kind == "ifdef":
            return payload in ctx.env
        if kind == "ifndef":
            return payload not in ctx.env
        return is_truthy(self._eval(payload, ctx, lineno))

    def _eval(self, text: str, ctx: _Ctx, lineno: int) -> Any:
        try:
            return evaluate(text, ctx.env)
        except MacroError as e:
            if e.file is None:
                raise MacroError(e.message, file=ctx.file, line=lineno) from None
            raise

    def _subst(self, text: str, ctx: _Ctx, lineno: int) -> str:
        parts: list[str] = []
        i = 0
        while True:
            start = text.find("@{", i)
            if start == -1:
                parts.append(text[i:])
                return "".join(parts)
            parts.append(text[i:start])
            close = self._find_close(text, start + 2, ctx, lineno)
            value = self._eval(text[start + 2 : close], ctx, lineno)
            parts.append(value_to_text(value))
            i = close + 1

    def _find_close(self, text: str, start: int, ctx: _Ctx, lineno: int) -> int:
        depth, i, quote = 1, start, ""
        while i < len(text):
            c = text[i]
            if quote:
                if c == quote:
                    quote = ""
            elif c in "\"'":
                quote = c
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return i
            i += 1
        raise MacroError("unterminated @{...} expansion", file=ctx.file, line=lineno)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _finish(exp: _Expander) -> tuple[str, LineMap]:
    text = "\n".join(exp.out)
    if exp.out:
        text += "\n"
    return text, exp.linemap


def expand(path: str | Path) -> tuple[str, LineMap]:
    """Expand the macro directives in the file at ``path``.

    Returns the fully-expanded text and a :class:`LineMap` pointing each
    output line back to its origin in the user's source.
    """
    path = Path(path)
    exp = _Expander()
    exp.include_stack.append(path.resolve())
    exp.run(path.read_text(), _Ctx({}, str(path), path.parent, ()))
    return _finish(exp)


def expand_string(
    text: str,
    *,
    filename: str = "<string>",
    base_dir: str | Path | None = None,
    env: dict | None = None,
) -> tuple[str, LineMap]:
    """Expand macro directives in ``text``.

    ``base_dir`` resolves relative ``@#include`` paths (default: cwd);
    ``env`` seeds the macro environment. Chiefly for tests and for
    inspecting expansion without a file on disk.
    """
    base = Path(base_dir) if base_dir is not None else Path.cwd()
    exp = _Expander()
    exp.run(text, _Ctx(dict(env or {}), filename, base, ()))
    return _finish(exp)

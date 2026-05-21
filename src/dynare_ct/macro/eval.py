"""Hand-rolled evaluator for the macro expression language.

The macro language is a small, dynamically-typed expression language --
distinct from and far simpler than the modelling language. Values are
integers, floats, booleans, strings and (possibly nested) lists thereof.

Pipeline: :func:`tokenize` -> :func:`_Parser` (recursive descent into a
tiny tuple-based AST) -> :func:`_eval` (tree walk against an environment).
The public surface is :func:`evaluate`, plus :func:`is_truthy` and
:func:`value_to_text` used by the expansion driver.

Grammar, lowest to highest precedence::

    expr    := or
    or      := and ('||' and)*
    and     := cmp ('&&' cmp)*
    cmp     := range (('=='|'!='|'<'|'<='|'>'|'>='|'in') range)?
    range   := add (':' add)?
    add     := mul (('+'|'-') mul)*
    mul     := unary (('*'|'/') unary)*
    unary   := ('-'|'!') unary | power
    power   := postfix ('^' unary)?          # right-associative
    postfix := atom ('[' expr ']')*          # 1-based indexing
    atom    := NUMBER | STRING | bool | array | call | var | '(' expr ')'
    array   := '[' (expr (',' expr)*)? ']'
    call    := IDENT '(' (expr (',' expr)*)? ')'

Indexing and ranges follow Dynare: arrays are 1-indexed and ``a:b`` is the
inclusive integer range.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

__all__ = [
    "MacroError",
    "MacroFunction",
    "evaluate",
    "is_truthy",
    "parse_expression",
    "value_to_text",
]


class MacroError(Exception):
    """A macro-layer error, optionally carrying a source position.

    The expression layer raises these without a position; the expansion
    driver attaches ``file``/``line`` as it unwinds.
    """

    def __init__(self, message: str, *, file: str | None = None, line: int | None = None):
        self.message = message
        self.file = file
        self.line = line
        super().__init__(self._render())

    def _render(self) -> str:
        if self.file is not None and self.line is not None:
            return f"{self.file}:{self.line}: {self.message}"
        if self.line is not None:
            return f"line {self.line}: {self.message}"
        return self.message


@dataclass(frozen=True)
class MacroFunction:
    """A user-defined function macro: ``@#define f(params) = body``.

    ``body`` is the pre-parsed expression AST. Free variables in the body
    resolve against the environment at *call* time, so a function may
    reference macro variables defined after it.
    """

    params: tuple[str, ...]
    body: tuple


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

# Two-character operators must precede their single-character prefixes.
_OPERATORS = (
    "||",
    "&&",
    "==",
    "!=",
    "<=",
    ">=",
    "<",
    ">",
    "!",
    "+",
    "-",
    "*",
    "/",
    "^",
    ":",
    "(",
    ")",
    "[",
    "]",
    ",",
)

_NUMBER_RE = re.compile(r"\d+\.\d*([eE][+-]?\d+)?|\.\d+([eE][+-]?\d+)?|\d+([eE][+-]?\d+)?")
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class _Token:
    __slots__ = ("kind", "value", "col")

    def __init__(self, kind: str, value: Any, col: int):
        self.kind = kind  # 'num' | 'str' | 'ident' | 'op'
        self.value = value
        self.col = col


def tokenize(text: str) -> list[_Token]:
    """Split a macro expression into tokens."""
    tokens: list[_Token] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
            continue
        if c in "\"'":
            j = text.find(c, i + 1)
            if j == -1:
                raise MacroError(f"unterminated string literal at column {i + 1}")
            tokens.append(_Token("str", text[i + 1 : j], i))
            i = j + 1
            continue
        if c.isdigit() or (c == "." and i + 1 < n and text[i + 1].isdigit()):
            m = _NUMBER_RE.match(text, i)
            assert m is not None
            raw = m.group()
            value: Any = float(raw) if any(ch in raw for ch in ".eE") else int(raw)
            tokens.append(_Token("num", value, i))
            i = m.end()
            continue
        m = _IDENT_RE.match(text, i)
        if m is not None:
            tokens.append(_Token("ident", m.group(), i))
            i = m.end()
            continue
        for op in _OPERATORS:
            if text.startswith(op, i):
                tokens.append(_Token("op", op, i))
                i += len(op)
                break
        else:
            raise MacroError(f"unexpected character {c!r} at column {i + 1}")
    return tokens


# ---------------------------------------------------------------------------
# Parser: tokens -> tuple-based AST
#
# Node shapes:
#   ("lit", value)            ("var", name)
#   ("array", [node, ...])    ("call", name, [node, ...])
#   ("index", target, index)  ("unary", op, node)
#   ("bin", op, left, right)  ("range", lo, hi)
# ---------------------------------------------------------------------------

_BOOLEANS = {"true": True, "false": False, "TRUE": True, "FALSE": False}
_COMPARISONS = {"==", "!=", "<", "<=", ">", ">="}


class _Parser:
    def __init__(self, tokens: list[_Token]):
        self._toks = tokens
        self._pos = 0

    def parse(self) -> tuple:
        node = self._or()
        if self._pos != len(self._toks):
            tok = self._toks[self._pos]
            raise MacroError(f"unexpected {tok.value!r} in expression")
        return node

    # -- token helpers ------------------------------------------------------

    def _peek(self) -> _Token | None:
        return self._toks[self._pos] if self._pos < len(self._toks) else None

    def _is_op(self, *ops: str) -> bool:
        tok = self._peek()
        return tok is not None and tok.kind == "op" and tok.value in ops

    def _is_kw(self, word: str) -> bool:
        tok = self._peek()
        return tok is not None and tok.kind == "ident" and tok.value == word

    def _advance(self) -> _Token:
        tok = self._toks[self._pos]
        self._pos += 1
        return tok

    def _expect_op(self, op: str) -> None:
        if not self._is_op(op):
            raise MacroError(f"expected {op!r} in expression")
        self._advance()

    # -- grammar ------------------------------------------------------------

    def _or(self) -> tuple:
        node = self._and()
        while self._is_op("||"):
            self._advance()
            node = ("bin", "||", node, self._and())
        return node

    def _and(self) -> tuple:
        node = self._cmp()
        while self._is_op("&&"):
            self._advance()
            node = ("bin", "&&", node, self._cmp())
        return node

    def _cmp(self) -> tuple:
        node = self._range()
        if self._peek() is not None and (self._is_op(*_COMPARISONS) or self._is_kw("in")):
            op = self._advance().value
            node = ("bin", op, node, self._range())
        return node

    def _range(self) -> tuple:
        node = self._add()
        if self._is_op(":"):
            self._advance()
            node = ("range", node, self._add())
        return node

    def _add(self) -> tuple:
        node = self._mul()
        while self._is_op("+", "-"):
            op = self._advance().value
            node = ("bin", op, node, self._mul())
        return node

    def _mul(self) -> tuple:
        node = self._unary()
        while self._is_op("*", "/"):
            op = self._advance().value
            node = ("bin", op, node, self._unary())
        return node

    def _unary(self) -> tuple:
        if self._is_op("-", "!"):
            op = self._advance().value
            return ("unary", op, self._unary())
        return self._power()

    def _power(self) -> tuple:
        node = self._postfix()
        if self._is_op("^"):
            self._advance()
            return ("bin", "^", node, self._unary())  # right-associative
        return node

    def _postfix(self) -> tuple:
        node = self._atom()
        while self._is_op("["):
            self._advance()
            index = self._or()
            self._expect_op("]")
            node = ("index", node, index)
        return node

    def _atom(self) -> tuple:
        tok = self._peek()
        if tok is None:
            raise MacroError("unexpected end of expression")
        if tok.kind == "num" or tok.kind == "str":
            self._advance()
            return ("lit", tok.value)
        if tok.kind == "ident":
            self._advance()
            if tok.value in _BOOLEANS:
                return ("lit", _BOOLEANS[tok.value])
            if self._is_op("("):
                self._advance()
                args = self._arg_list()
                self._expect_op(")")
                return ("call", tok.value, args)
            return ("var", tok.value)
        if tok.kind == "op" and tok.value == "[":
            self._advance()
            items = self._arg_list()
            self._expect_op("]")
            return ("array", items)
        if tok.kind == "op" and tok.value == "(":
            self._advance()
            node = self._or()
            self._expect_op(")")
            return node
        raise MacroError(f"unexpected {tok.value!r} in expression")

    def _arg_list(self) -> list[tuple]:
        items: list[tuple] = []
        if self._is_op(")", "]"):
            return items
        items.append(self._or())
        while self._is_op(","):
            self._advance()
            items.append(self._or())
        return items


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------


def _length(args: list) -> int:
    if len(args) != 1 or not isinstance(args[0], (list, str)):
        raise MacroError("length() expects a single list or string argument")
    return len(args[0])


def _range(args: list) -> list[int]:
    if not (2 <= len(args) <= 3) or not all(isinstance(a, int) for a in args):
        raise MacroError("range() expects 2 or 3 integer arguments")
    lo, hi = args[0], args[1]
    step = args[2] if len(args) == 3 else 1
    if step == 0:
        raise MacroError("range() step must be non-zero")
    return list(range(lo, hi + (1 if step > 0 else -1), step))


# --- real-math library ----------------------------------------------------
#
# Functions that produce a real always return a float; the rounding family
# (floor/ceil/round/trunc/sign) returns an integer, and abs/min/max/mod/power
# preserve the integer-ness of their operands so results stay usable as
# indices and loop bounds.


def _expect_numeric(name: str, args: list, n: int | None = None) -> list:
    if n is not None and len(args) != n:
        raise MacroError(f"{name}() expects {n} argument(s), got {len(args)}")
    for a in args:
        if not _is_number(a):
            raise MacroError(f"{name}() expects numeric argument(s)")
    return args


def _unary_math(name: str, fn):
    """Wrap a one-argument math function, mapping domain errors to MacroError."""

    def builtin(args: list):
        (x,) = _expect_numeric(name, args, 1)
        try:
            return fn(float(x))
        except (ValueError, OverflowError) as exc:
            raise MacroError(f"{name}(): {exc}") from None

    return builtin


def _abs(args: list):
    (x,) = _expect_numeric("abs", args, 1)
    return abs(x)


def _sign(args: list) -> int:
    (x,) = _expect_numeric("sign", args, 1)
    return (x > 0) - (x < 0)


def _floor(args: list) -> int:
    (x,) = _expect_numeric("floor", args, 1)
    return math.floor(x)


def _ceil(args: list) -> int:
    (x,) = _expect_numeric("ceil", args, 1)
    return math.ceil(x)


def _trunc(args: list) -> int:
    (x,) = _expect_numeric("trunc", args, 1)
    return math.trunc(x)


def _round(args: list) -> int:
    # Round half away from zero (as in Dynare/MATLAB), not banker's rounding.
    (x,) = _expect_numeric("round", args, 1)
    return math.floor(x + 0.5) if x >= 0 else math.ceil(x - 0.5)


def _mod(args: list):
    a, b = _expect_numeric("mod", args, 2)
    if b == 0:
        raise MacroError("mod() by zero")
    return a - b * math.floor(a / b)  # divisor sign, like MATLAB mod


def _power(args: list):
    a, b = _expect_numeric("power", args, 2)
    return _arith("^", a, b)


def _minmax(name: str, fn):
    def builtin(args: list):
        items = args[0] if len(args) == 1 and isinstance(args[0], list) else args
        if not items:
            raise MacroError(f"{name}() of an empty sequence")
        for a in items:
            if not _is_number(a):
                raise MacroError(f"{name}() expects numeric argument(s)")
        return fn(items)

    return builtin


def _norm_args(name: str, args: list) -> tuple[float, float, float]:
    if len(args) not in (1, 3):
        raise MacroError(f"{name}() expects 1 or 3 arguments")
    _expect_numeric(name, args)
    mu, sigma = (args[1], args[2]) if len(args) == 3 else (0.0, 1.0)
    if sigma <= 0:
        raise MacroError(f"{name}(): sigma must be positive")
    return args[0], mu, sigma


def _normpdf(args: list) -> float:
    x, mu, sigma = _norm_args("normpdf", args)
    z = (x - mu) / sigma
    return math.exp(-0.5 * z * z) / (sigma * math.sqrt(2 * math.pi))


def _normcdf(args: list) -> float:
    x, mu, sigma = _norm_args("normcdf", args)
    return 0.5 * (1.0 + math.erf((x - mu) / (sigma * math.sqrt(2.0))))


# One-argument functions that map directly onto the math module.
_REAL_UNARY = {
    "exp": math.exp,
    "ln": math.log,
    "log": math.log,
    "log10": math.log10,
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "erf": math.erf,
    "erfc": math.erfc,
}

_BUILTINS = {
    "length": _length,
    "range": _range,
    "abs": _abs,
    "sign": _sign,
    "floor": _floor,
    "ceil": _ceil,
    "trunc": _trunc,
    "round": _round,
    "mod": _mod,
    "power": _power,
    "min": _minmax("min", min),
    "max": _minmax("max", max),
    "normpdf": _normpdf,
    "normcdf": _normcdf,
    **{name: _unary_math(name, fn) for name, fn in _REAL_UNARY.items()},
}


def is_truthy(value: Any) -> bool:
    """Interpret a macro value as a condition (booleans and numbers only)."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    raise MacroError(f"condition must be boolean or numeric, got {_typename(value)}")


def value_to_text(value: Any) -> str:
    """Render a macro value for inline ``@{...}`` substitution."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, (int, str)):
        return str(value)
    if isinstance(value, list):
        return ", ".join(value_to_text(v) for v in value)
    raise MacroError(f"cannot render value of type {_typename(value)}")


def parse_expression(text: str) -> tuple:
    """Parse a macro expression into its internal AST without evaluating.

    Used to capture a function-macro body once at definition time.
    """
    return _Parser(tokenize(text)).parse()


def evaluate(text: str, env: Mapping[str, Any]) -> Any:
    """Parse and evaluate a macro expression against ``env``."""
    return _eval(parse_expression(text), env)


def _eval(node: tuple, env: Mapping[str, Any]) -> Any:
    tag = node[0]
    if tag == "lit":
        return node[1]
    if tag == "var":
        name = node[1]
        if name not in env:
            raise MacroError(f"undefined macro variable {name!r}")
        return env[name]
    if tag == "array":
        return [_eval(item, env) for item in node[1]]
    if tag == "call":
        name, arg_nodes = node[1], node[2]
        args = [_eval(a, env) for a in arg_nodes]
        func = env.get(name)
        if isinstance(func, MacroFunction):
            return _call_function(name, func, args, env)
        if name in env:
            raise MacroError(f"{name!r} is not a macro function")
        if name in _BUILTINS:
            return _BUILTINS[name](args)
        raise MacroError(f"unknown macro function {name!r}")
    if tag == "index":
        return _index(_eval(node[1], env), _eval(node[2], env))
    if tag == "unary":
        return _unary(node[1], _eval(node[2], env))
    if tag == "range":
        return _range([_eval(node[1], env), _eval(node[2], env)])
    if tag == "bin":
        return _binary(node[1], node[2], node[3], env)
    raise MacroError(f"internal: unknown node {tag!r}")  # pragma: no cover


def _call_function(name: str, func: MacroFunction, args: list, env: Mapping[str, Any]) -> Any:
    if len(args) != len(func.params):
        raise MacroError(
            f"macro function {name!r} expects {len(func.params)} argument(s), got {len(args)}"
        )
    # Parameters shadow the call-time environment; free variables fall
    # through to it (late binding).
    local = dict(env)
    local.update(zip(func.params, args, strict=True))
    return _eval(func.body, local)


def _unary(op: str, value: Any) -> Any:
    if op == "-":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise MacroError(f"cannot negate {_typename(value)}")
        return -value
    # op == "!"
    return not is_truthy(value)


def _index(target: Any, index: Any) -> Any:
    if not isinstance(target, (list, str)):
        raise MacroError(f"cannot index into {_typename(target)}")
    if isinstance(index, bool) or not isinstance(index, int):
        raise MacroError("index must be an integer")
    if not 1 <= index <= len(target):
        raise MacroError(f"index {index} out of range (1..{len(target)})")
    return target[index - 1]


def _binary(op: str, left_node: tuple, right_node: tuple, env: Mapping[str, Any]) -> Any:
    # Short-circuit logical operators evaluate the right operand lazily.
    if op == "&&":
        return is_truthy(_eval(left_node, env)) and is_truthy(_eval(right_node, env))
    if op == "||":
        return is_truthy(_eval(left_node, env)) or is_truthy(_eval(right_node, env))

    left = _eval(left_node, env)
    right = _eval(right_node, env)

    if op == "==":
        return left == right
    if op == "!=":
        return left != right
    if op == "in":
        if not isinstance(right, (list, str)):
            raise MacroError(
                f"right operand of 'in' must be a list or string, got {_typename(right)}"
            )
        return left in right
    if op in ("<", "<=", ">", ">="):
        return _compare(op, left, right)
    return _arith(op, left, right)


def _compare(op: str, left: Any, right: Any) -> bool:
    if not _same_ordered_kind(left, right):
        raise MacroError(f"cannot compare {_typename(left)} with {_typename(right)}")
    if op == "<":
        return left < right
    if op == "<=":
        return left <= right
    if op == ">":
        return left > right
    return left >= right  # ">="


def _arith(op: str, left: Any, right: Any) -> Any:
    if op == "+":
        if isinstance(left, str) and isinstance(right, str):
            return left + right
        if isinstance(left, list) and isinstance(right, list):
            return left + right
    if not (_is_number(left) and _is_number(right)):
        raise MacroError(
            f"operator {op!r} not defined for {_typename(left)} and {_typename(right)}"
        )
    both_int = isinstance(left, int) and isinstance(right, int)
    if op == "+":
        return left + right
    if op == "-":
        return left - right
    if op == "*":
        return left * right
    if op == "/":
        if right == 0:
            raise MacroError("division by zero")
        if both_int and left % right == 0:
            return left // right
        return left / right
    if op == "^":
        result = left**right
        return int(result) if both_int and right >= 0 else result
    raise MacroError(f"internal: unknown operator {op!r}")  # pragma: no cover


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _same_ordered_kind(left: Any, right: Any) -> bool:
    if isinstance(left, str) and isinstance(right, str):
        return True
    return _is_number(left) and _is_number(right)


def _typename(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "real"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, MacroFunction):
        return "function"
    return type(value).__name__

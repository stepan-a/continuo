"""Shocks: validating exogenous belief paths and revelation structure.

Each ``shocks`` entry drives one ``varexo`` with a sequence of
(reveal time, expected path) beliefs. At each reveal time agents replace
their belief about the shock's whole future path; the realised path is
the piecewise concatenation.

This pass checks that each entry names a declared ``varexo``, normalises
the bare ``path = …`` sugar to ``path at t=0``, forbids mixing that sugar
with an explicit ``path at t=0`` for the same shock, rejects duplicate
reveal times, and orders the beliefs by reveal time. Reveal times given
as a non-literal expression (e.g. a parameter) flow through unsorted and
without numeric duplicate detection; the never-arriving check for
``t >= T`` needs the simulation horizon and is left to the orchestrator.
"""

from __future__ import annotations

from dataclasses import replace

from continuo.ir.errors import IRError
from continuo.ir.model import Model, Shock, ShockPath
from continuo.parser.ast import (
    Expr,
    ModelFile,
    NumberLit,
    ShockEntry,
    ShocksBlock,
    UnaryOp,
)

__all__ = ["attach_shocks"]


def attach_shocks(model: Model, model_file: ModelFile) -> Model:
    """Validate the shocks block and attach the belief paths to the model."""
    blocks = [s for s in model_file.statements if isinstance(s, ShocksBlock)]
    if len(blocks) > 1:
        raise IRError("more than one shocks block", blocks[1].pos)
    if not blocks:
        return replace(model, shocks=())
    seen: set[str] = set()
    shocks: list[Shock] = []
    for entry in blocks[0].entries:
        name = _shock_name(model, entry)
        if name in seen:
            raise IRError(f"duplicate shocks entry for {name!r}", entry.name.pos)
        seen.add(name)
        shocks.append(_shock(name, entry))
    return replace(model, shocks=tuple(shocks))


def _shock_name(model: Model, entry: ShockEntry) -> str:
    name = entry.name.name
    if model.is_exogenous(name):
        return name
    if model.kind_of(name) is not None:
        raise IRError(f"{name!r} is endogenous; only a varexo can carry a shock", entry.name.pos)
    if model.is_parameter(name):
        raise IRError(f"{name!r} is a parameter; only a varexo can carry a shock", entry.name.pos)
    raise IRError(f"shock on undeclared variable {name!r}", entry.name.pos)


def _shock(name: str, entry: ShockEntry) -> Shock:
    # (literal value or None, ShockPath, position) per belief.
    items: list[tuple[float | None, ShockPath, object]] = []
    saw_bare = False
    explicit_zero = False
    for assignment in entry.paths:
        if assignment.reveal_time is None:  # bare `path = …`
            saw_bare = True
            reveal: Expr = NumberLit(0.0)
            value: float | None = 0.0
        else:
            reveal = assignment.reveal_time
            value = _literal(assignment.reveal_time)
            if value == 0.0:
                explicit_zero = True
        items.append((value, ShockPath(reveal, assignment.path), assignment.pos))

    if saw_bare and explicit_zero:
        raise IRError(
            f"shock {name!r}: mixing 'path = …' with explicit 'path at t=0 = …' is not allowed",
            entry.pos,
        )
    _reject_duplicate_reveal_times(name, items)

    if all(value is not None for value, _, _ in items):
        items.sort(key=lambda item: item[0])
    return Shock(name, tuple(path for _, path, _ in items))


def _reject_duplicate_reveal_times(name: str, items: list) -> None:
    seen: set[float] = set()
    for value, _, pos in items:
        if value is None:
            continue
        if value in seen:
            raise IRError(f"shock {name!r}: duplicate path at t={_format(value)}", pos)
        seen.add(value)


def _literal(expr: Expr) -> float | None:
    """The numeric value of a reveal-time expression, or None if not a literal."""
    if isinstance(expr, NumberLit):
        return expr.value
    if isinstance(expr, UnaryOp) and expr.op == "-" and isinstance(expr.operand, NumberLit):
        return -expr.operand.value
    return None


def _format(value: float) -> str:
    return str(int(value)) if value == int(value) else str(value)

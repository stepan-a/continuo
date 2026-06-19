"""Variable-classification consistency checks.

The class of every endogenous variable is declared explicitly
(``var(state)``, ``var(jump)``, or bare ``var`` for algebraic). This pass
checks that the declared classes are consistent with how the variables
are used in the equations:

- every state and jump has its time derivative ``diff(·)`` somewhere, and
  no algebraic variable does;
- the number of equations carrying a ``diff`` equals ``#states + #jumps``,
  and the system is square (one equation per endogenous variable);
- no variable is both pinned by an algebraic equation (bare on the LHS)
  and differentiated elsewhere (over-determined).

A time derivative is written ``diff(x)`` or ``diff(x, p)`` (and nested
``diff(diff(x))``); its subject must be a single variable.
"""

from __future__ import annotations

from continuo.ir._exprtools import walk
from continuo.ir.errors import IRError
from continuo.ir.model import Model
from continuo.parser.ast import (
    Equation,
    Expr,
    FunctionCall,
    Identifier,
    SourcePos,
    VarKind,
)

__all__ = ["classify"]


def classify(model: Model) -> None:
    """Run the classification checks, raising :class:`IRError` on the first failure."""
    diff_targets, n_diff_eqs, bare_lhs = _scan(model.equations)
    _check_diff_classes(model, diff_targets)
    _check_all_dynamic_differentiated(model, diff_targets)
    _check_not_overdetermined(diff_targets, bare_lhs)
    _check_counts(model, n_diff_eqs)


def _scan(
    equations: tuple[Equation, ...],
) -> tuple[dict[str, SourcePos | None], int, dict[str, SourcePos | None]]:
    """Collect diff subjects, the count of dynamic equations, and bare LHS names."""
    diff_targets: dict[str, SourcePos | None] = {}
    bare_lhs: dict[str, SourcePos | None] = {}
    n_diff_eqs = 0
    for eq in equations:
        calls = _diff_calls(eq.rhs)
        if eq.lhs is not None:
            calls += _diff_calls(eq.lhs)
        if calls:
            n_diff_eqs += 1
        for call in calls:
            ident = _diff_subject(call)
            diff_targets.setdefault(ident.name, ident.pos)
        if isinstance(eq.lhs, Identifier):
            bare_lhs.setdefault(eq.lhs.name, eq.lhs.pos)
    return diff_targets, n_diff_eqs, bare_lhs


def _diff_calls(expr: Expr) -> list[FunctionCall]:
    return [n for n in walk(expr) if isinstance(n, FunctionCall) and n.name.name == "diff"]


def _diff_subject(call: FunctionCall) -> Identifier:
    """The variable a ``diff`` differentiates, descending through nested diffs."""
    arg: Expr | None = call.args[0] if call.args else None
    while isinstance(arg, FunctionCall) and arg.name.name == "diff":
        arg = arg.args[0] if arg.args else None
    if not isinstance(arg, Identifier):
        raise IRError("diff() expects a variable as its first argument", call.pos)
    return arg


def _check_diff_classes(model: Model, diff_targets: dict[str, SourcePos | None]) -> None:
    """Every differentiated name must be a state or jump."""
    for name, pos in diff_targets.items():
        kind = model.kind_of(name)
        if kind in (VarKind.STATE, VarKind.JUMP):
            continue
        if kind is VarKind.ALGEBRAIC:
            raise IRError(
                f"{name!r} is declared algebraic but its time derivative "
                f"diff({name}) appears; declare it var(state) or var(jump)",
                pos,
            )
        if model.is_exogenous(name):
            raise IRError(f"cannot take the time derivative of exogenous variable {name!r}", pos)
        if model.is_parameter(name):
            raise IRError(f"cannot take the time derivative of parameter {name!r}", pos)
        raise IRError(f"diff() of undeclared variable {name!r}", pos)


def _check_all_dynamic_differentiated(
    model: Model, diff_targets: dict[str, SourcePos | None]
) -> None:
    """Every state and jump must actually be differentiated somewhere."""
    for name in model.states + model.jumps:
        if name not in diff_targets:
            kind = model.kind_of(name).value  # type: ignore[union-attr]
            raise IRError(
                f"{kind} {name!r} is declared but its time derivative "
                f"diff({name}) never appears in the model"
            )


def _check_not_overdetermined(
    diff_targets: dict[str, SourcePos | None], bare_lhs: dict[str, SourcePos | None]
) -> None:
    """A variable cannot be both algebraically pinned and differentiated."""
    for name, pos in bare_lhs.items():
        if name in diff_targets:
            raise IRError(
                f"{name!r} is defined by an algebraic equation but its time "
                f"derivative diff({name}) also appears (over-determined)",
                pos,
            )


def _check_counts(model: Model, n_diff_eqs: int) -> None:
    n_eqs = len(model.equations)
    n_endogenous = len(model.endogenous)
    if n_eqs != n_endogenous:
        raise IRError(f"model has {n_eqs} equation(s) but {n_endogenous} endogenous variable(s)")
    n_dynamic = len(model.states) + len(model.jumps)
    if n_diff_eqs != n_dynamic:
        raise IRError(
            f"expected {n_dynamic} dynamic equation(s) (one per state/jump, each "
            f"carrying diff) but found {n_diff_eqs}"
        )

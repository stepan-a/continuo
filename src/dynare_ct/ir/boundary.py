"""Boundary data: initial conditions and the optional starting iterate.

``initval`` gives the left boundary of the BVP — the initial value of each
*state* variable (jumps and algebraic variables are determined by the
model and the terminal steady state, so they must not appear). A
higher-order state's derivatives are set with ``diff(x)`` / ``diff(x, k)``
on the LHS, which map to the auxiliary states the reduction pass
introduced (``__aux_diff_x_k``).

``initval(steady)`` is sugar: every state not given an explicit value is
filled from the initial steady state — ``steady_state(x)`` (carrying the
optional ``e={…}`` exogenous override), or ``0`` for an auxiliary
derivative state, which is zero in steady state.

``initial_guess`` is a separate, optional starting iterate for the
nonlinear solvers; it may name any endogenous variable and need not be
complete.

When an ``initval`` block is present (and not ``(steady)``) it must cover
every state. A model with no ``initval`` still builds here; the
requirement that a *runnable* model supply initial conditions is enforced
when a simulation is requested.
"""

from __future__ import annotations

from dataclasses import replace

from dynare_ct.ir.errors import IRError
from dynare_ct.ir.model import Model
from dynare_ct.parser.ast import (
    DictLiteral,
    Expr,
    FunctionCall,
    Identifier,
    InitialGuessBlock,
    InitvalBlock,
    KeywordArg,
    ModelFile,
    NumberLit,
    SourcePos,
    VarKind,
)

__all__ = ["attach_boundary"]

_AUX_PREFIX = "__aux_diff_"


def attach_boundary(model: Model, model_file: ModelFile) -> Model:
    """Validate the boundary blocks and attach the resulting data to the model."""
    initval = _single(model_file, InitvalBlock, "initval")
    guess = _single(model_file, InitialGuessBlock, "initial_guess")
    return replace(
        model,
        initial_values=_initial_values(model, initval),
        initial_guess=_initial_guess(model, guess),
    )


def _single(model_file: ModelFile, cls: type, name: str):
    found = [s for s in model_file.statements if isinstance(s, cls)]
    if len(found) > 1:
        raise IRError(f"more than one {name} block", found[1].pos)
    return found[0] if found else None


# ---------------------------------------------------------------------------
# initval
# ---------------------------------------------------------------------------


def _initial_values(model: Model, block: InitvalBlock | None) -> dict[str, Expr]:
    if block is None:
        return {}
    e_override = _steady_e(block)
    values: dict[str, Expr] = {}
    for assignment in block.assignments:
        target, pos = _initval_target(model, assignment.lhs)
        if target in values:
            raise IRError(f"duplicate initial value for {_display(target)!r}", pos)
        values[target] = assignment.rhs
    for state in model.states:
        if state in values:
            continue
        if block.steady:
            values[state] = _steady_fill(state, e_override)
        else:
            raise IRError(f"state {_display(state)!r} has no initial value in initval")
    return values


def _steady_e(block: InitvalBlock) -> DictLiteral | None:
    if not block.steady:
        if block.kwargs:
            raise IRError("initval qualifier arguments require '(steady)'", block.pos)
        return None
    e_override: DictLiteral | None = None
    for kw in block.kwargs:
        if kw.name.name != "e":
            raise IRError(f"unknown initval(steady) argument {kw.name.name!r}", kw.pos)
        if not isinstance(kw.value, DictLiteral):
            raise IRError("initval(steady) 'e' must be a {…} mapping", kw.pos)
        e_override = kw.value
    return e_override


def _steady_fill(state: str, e_override: DictLiteral | None) -> Expr:
    if state.startswith(_AUX_PREFIX):
        return NumberLit(0.0)  # a derivative is zero in steady state
    kwargs = [KeywordArg(Identifier("e"), e_override)] if e_override is not None else []
    return FunctionCall(Identifier("steady_state"), [Identifier(state)], kwargs)


def _initval_target(model: Model, lhs: Expr) -> tuple[str, SourcePos | None]:
    if isinstance(lhs, Identifier):
        if model.kind_of(lhs.name) is not VarKind.STATE:
            raise IRError(
                f"only states may appear in initval; {lhs.name!r} is {_describe(model, lhs.name)}",
                lhs.pos,
            )
        return lhs.name, lhs.pos
    if isinstance(lhs, FunctionCall) and lhs.name.name == "diff":
        base, order = _diff_lhs(lhs)
        target = base.name if order == 0 else f"{_AUX_PREFIX}{base.name}_{order}"
        if target not in model.states:
            raise IRError(
                f"diff({base.name}) has no initial condition: {base.name!r} is not "
                "a state with a derivative of that order",
                lhs.pos,
            )
        return target, lhs.pos
    raise IRError(
        "invalid initval entry; expected 'state = …' or 'diff(state) = …'",
        getattr(lhs, "pos", None),
    )


def _diff_lhs(call: FunctionCall) -> tuple[Identifier, int]:
    if not call.args or not isinstance(call.args[0], Identifier):
        raise IRError("diff() in initval expects a variable", call.pos)
    if len(call.args) > 2:
        raise IRError("diff() takes one or two arguments", call.pos)
    order = 1
    if len(call.args) == 2:
        node = call.args[1]
        if not isinstance(node, NumberLit) or node.value != int(node.value) or node.value < 0:
            raise IRError("diff() order in initval must be a non-negative integer", call.pos)
        order = int(node.value)
    return call.args[0], order


# ---------------------------------------------------------------------------
# initial_guess
# ---------------------------------------------------------------------------


def _initial_guess(model: Model, block: InitialGuessBlock | None) -> dict[str, Expr]:
    if block is None:
        return {}
    guess: dict[str, Expr] = {}
    for assignment in block.assignments:
        lhs = assignment.lhs
        if not isinstance(lhs, Identifier):
            raise IRError("initial_guess entries must be 'variable = …'", getattr(lhs, "pos", None))
        if model.kind_of(lhs.name) is None:
            raise IRError(
                f"initial_guess for {lhs.name!r}, which is not an endogenous variable",
                lhs.pos,
            )
        if lhs.name in guess:
            raise IRError(f"duplicate initial_guess for {lhs.name!r}", lhs.pos)
        guess[lhs.name] = assignment.rhs
    return guess


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _describe(model: Model, name: str) -> str:
    kind = model.kind_of(name)
    if kind is VarKind.JUMP:
        return "a jump"
    if kind is VarKind.ALGEBRAIC:
        return "algebraic"
    if model.is_exogenous(name):
        return "exogenous"
    if model.is_parameter(name):
        return "a parameter"
    return "not declared"


def _display(state: str) -> str:
    """Render an auxiliary derivative state back as diff(x[, k]) for messages."""
    if not state.startswith(_AUX_PREFIX):
        return state
    base, _, order = state[len(_AUX_PREFIX) :].rpartition("_")
    return f"diff({base})" if order == "1" else f"diff({base}, {order})"

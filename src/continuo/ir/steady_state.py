"""The analytical steady state: validating the steady_state_model block.

``steady_state_model`` defines ``x_ss = h(theta, e)`` — each endogenous
variable's steady value as a function of the parameters and the exogenous
values the orchestrator supplies. Only declared endogenous variables may
appear on the LHS (an ``varexo`` denotes a supplied exogenous value and so
may appear on the RHS but never the LHS; parameters cannot be assigned).

When the block is present it must be complete: every declared endogenous
variable needs a definition. The machine-introduced auxiliary derivative
states (``__aux_diff_x_k``) are not the user's to define — a derivative is
zero in steady state, so they are filled with ``0`` automatically.

When the block is absent the model still builds; the orchestrator falls
back to a numerical steady-state solve.
"""

from __future__ import annotations

from dataclasses import replace

from continuo.ir.errors import IRError
from continuo.ir.model import Model
from continuo.parser.ast import (
    Expr,
    Identifier,
    ModelFile,
    NumberLit,
    SteadyStateModelBlock,
)

__all__ = ["attach_steady_state"]


def attach_steady_state(model: Model, model_file: ModelFile) -> Model:
    """Validate the steady_state_model block and attach it to the model."""
    blocks = [s for s in model_file.statements if isinstance(s, SteadyStateModelBlock)]
    if len(blocks) > 1:
        raise IRError("more than one steady_state_model block", blocks[1].pos)
    block = blocks[0] if blocks else None
    return replace(model, steady_state=_steady_state(model, block))


def _steady_state(model: Model, block: SteadyStateModelBlock | None) -> dict[str, Expr]:
    if block is None:
        return {}
    defined: dict[str, Expr] = {}
    for assignment in block.assignments:
        name = _lhs_name(model, assignment.lhs)
        if name in defined:
            raise IRError(
                f"duplicate steady_state_model definition for {name!r}", assignment.lhs.pos
            )
        defined[name] = assignment.rhs

    missing = [v for v in model.endogenous if not model.is_auxiliary(v) and v not in defined]
    if missing:
        raise IRError(f"steady_state_model is incomplete: no definition for {', '.join(missing)}")

    # Auxiliary derivative states are zero in steady state.
    for name in model.endogenous:
        if model.is_auxiliary(name) and name not in defined:
            defined[name] = NumberLit(0.0)
    return defined


def _lhs_name(model: Model, lhs: Expr) -> str:
    if not isinstance(lhs, Identifier):
        raise IRError(
            "steady_state_model left-hand side must be a variable name",
            getattr(lhs, "pos", None),
        )
    name = lhs.name
    if model.kind_of(name) is not None:
        return name
    if model.is_exogenous(name):
        raise IRError(
            f"{name!r} is exogenous and may not be assigned in steady_state_model "
            "(exogenous values appear on the right-hand side)",
            lhs.pos,
        )
    if model.is_parameter(name):
        raise IRError(
            f"{name!r} is a parameter and may not be assigned in steady_state_model",
            lhs.pos,
        )
    raise IRError(f"steady_state_model assigns undeclared variable {name!r}", lhs.pos)

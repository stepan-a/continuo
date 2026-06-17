"""Change of variable for strict domain constraints on the steady state.

A variable declared with a domain constraint (``var(positive) K;`` etc.)
must stay strictly inside an open interval. Rather than constrain the
root-find, we reparametrise: solve in an unconstrained variable ``y`` and
map it through a smooth, invertible ``x = T(y)`` whose image is exactly the
open domain. The root-finder roams all of ``y``-space while ``x`` never
leaves ``(a, b)`` — so the residual never sees a ``NaN`` from ``x^alpha``
or ``log(x)`` outside the domain.

The four cases, from the numeric bounds ``a`` (lower) / ``b`` (upper):

==========  =======================  ====================  ===============
case        ``x = T(y)``             ``y = T⁻¹(x)``        ``T(0)``
==========  =======================  ====================  ===============
none        ``y``                    ``x``                 ``0``
lower ``a`` ``a + exp(y)``           ``log(x - a)``        ``a + 1``
upper ``b`` ``b - exp(y)``           ``log(b - x)``        ``b - 1``
both        ``a + (b-a)/(1+e^-y)``   ``log((x-a)/(b-x))``  midpoint
==========  =======================  ====================  ===============

The transform is built per solve (bounds may be parameter expressions),
then composed symbolically with the existing residual ``Function`` so that
CasADi automatic differentiation supplies ``∂F/∂y`` through the chain rule
— no manual ``dx/dy`` factor.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

import casadi as ca
import numpy as np

from continuo.codegen.residual import Residual
from continuo.ir.model import Model
from continuo.parser.ast import Expr
from continuo.solve.errors import SolveError
from continuo.solve.numeric import constant_table, eval_constant
from continuo.solve.rootfind import RootProblem

__all__ = ["VarTransform", "build_transforms", "build_constrained_problem"]


@dataclass(frozen=True)
class VarTransform:
    """The change of variable for one endogenous variable.

    ``lower`` / ``upper`` are the numeric bounds (``None`` for an open
    side); an unconstrained variable has both ``None`` and ``T`` is the
    identity. All maps act on a single scalar.
    """

    name: str
    lower: float | None
    upper: float | None

    @property
    def constrained(self) -> bool:
        return self.lower is not None or self.upper is not None

    def forward_sx(self, y: ca.SX) -> ca.SX:
        """``x = T(y)`` symbolically (uses :func:`casadi.exp`)."""
        a, b = self.lower, self.upper
        if a is not None and b is not None:
            return a + (b - a) / (1 + ca.exp(-y))
        if a is not None:
            return a + ca.exp(y)
        if b is not None:
            return b - ca.exp(y)
        return y

    def forward(self, y: float) -> float:
        """``x = T(y)`` numerically."""
        a, b = self.lower, self.upper
        if a is not None and b is not None:
            return a + (b - a) / (1 + math.exp(-y))
        if a is not None:
            return a + math.exp(y)
        if b is not None:
            return b - math.exp(y)
        return y

    def inverse(self, x: float) -> float:
        """``y = T⁻¹(x)``; raise :class:`SolveError` if ``x`` is outside the open domain."""
        a, b = self.lower, self.upper
        if a is not None and b is not None:
            if not (a < x < b):
                raise SolveError(self._outside(x, f"open interval ({a}, {b})"))
            return math.log((x - a) / (b - x))
        if a is not None:
            if not x > a:
                raise SolveError(self._outside(x, f"open domain (> {a})"))
            return math.log(x - a)
        if b is not None:
            if not x < b:
                raise SolveError(self._outside(x, f"open domain (< {b})"))
            return math.log(b - x)
        return x

    def default_interior(self) -> float:
        """The image ``T(0)`` of the unconstrained origin: a strictly interior point."""
        return self.forward(0.0)

    def _outside(self, x: float, domain: str) -> str:
        return (
            f"initial_guess for {self.name!r} is {x}, outside its {domain}; the "
            "starting iterate must be strictly interior to the declared domain"
        )


def build_transforms(
    model: Model, theta: dict[str, float], e: dict[str, float]
) -> list[VarTransform]:
    """One :class:`VarTransform` per endogenous variable, aligned with the ``x`` vector.

    Bound expressions are evaluated to numbers under the current parameter /
    exogenous values; an unconstrained variable gets the identity transform.
    Parameter-valued bounds are re-checked for ``lower < upper``.
    """
    table = constant_table(theta, e, model)
    transforms: list[VarTransform] = []
    for name in model.endogenous:
        bound = model.constraints.get(name)
        if bound is None:
            transforms.append(VarTransform(name, None, None))
            continue
        lo = _eval_bound(bound.lower, table, name, "lower")
        hi = _eval_bound(bound.upper, table, name, "upper")
        if lo is not None and hi is not None and lo >= hi:
            raise SolveError(
                f"empty domain for {name!r}: lower bound {lo} is not below upper bound {hi}"
            )
        transforms.append(VarTransform(name, lo, hi))
    return transforms


def _eval_bound(expr: Expr | None, table, name: str, side: str) -> float | None:
    if expr is None:
        return None
    return eval_constant(expr, table, what=f"{side} bound of {name!r}")


def build_constrained_problem(
    residual: Residual,
    xdot_zero: ca.DM,
    e_vec: ca.DM,
    theta_vec: ca.DM,
    transforms: list[VarTransform],
    y0: np.ndarray,
) -> tuple[RootProblem, Callable[[np.ndarray], np.ndarray]]:
    """Build the root problem in ``y``-space and the map back to ``x``.

    Composes ``x = T(y)`` with the residual ``Function`` and lets CasADi
    differentiate the composition, so ``∂F/∂y`` carries the chain-rule
    factor automatically. Returns the :class:`RootProblem` in ``y`` (with a
    CasADi ``residual_function`` for KINSOL) and ``untransform(y) = T(y)``.
    """
    n = len(transforms)
    y_sx = ca.SX.sym("y", n)
    x_of_y = ca.vertcat(*[t.forward_sx(y_sx[i]) for i, t in enumerate(transforms)])
    f_sx = residual.function(xdot_zero, x_of_y, e_vec, theta_vec, 0.0)
    j_sx = ca.jacobian(f_sx, y_sx)
    f_y = ca.Function("F_y", [y_sx], [f_sx], ["y"], ["F"])
    j_y = ca.Function("J_y", [y_sx], [j_sx], ["y"], ["J"])

    def g(y: np.ndarray) -> np.ndarray:
        return np.array(f_y(ca.DM(y))).reshape(-1)

    def jac(y: np.ndarray) -> np.ndarray:
        return np.array(j_y(ca.DM(y)))

    problem = RootProblem(
        g, jac, y0, residual_function=f_y, names=tuple(t.name for t in transforms)
    )

    def untransform(y: np.ndarray) -> np.ndarray:
        return np.array(
            [t.forward(float(yi)) for t, yi in zip(transforms, y, strict=True)], dtype=float
        )

    return problem, untransform

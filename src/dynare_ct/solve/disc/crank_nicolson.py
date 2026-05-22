"""Crank–Nicolson discretisation of the model residual.

For the implicit DAE ``F(ẋ, x, e, θ, t) = 0`` the second-order, A-stable
realisation is the implicit-midpoint rule (Crank–Nicolson; the two
coincide on linear problems): on the interval ``[tᵢ, tᵢ₊₁]`` the time
derivative of each dynamic variable is the difference quotient
``(xᵢ₊₁ − xᵢ)/dt`` and the state is the endpoint average
``(xᵢ + xᵢ₊₁)/2``, with ``F`` evaluated at the interval midpoint.

This module builds the per-interval residual as a CasADi ``Function``.
The perfect-foresight driver stacks these across the grid, taking the
dynamic rows as collocation equations and enforcing the algebraic rows
pointwise, and adds the boundary conditions.

Endogenous ordering is states, then jumps, then algebraic, so the first
``#states + #jumps`` entries of ``x`` are exactly the variables with a
time derivative — the ones the difference quotient applies to.
"""

from __future__ import annotations

import casadi as ca

from dynare_ct.codegen.residual import Residual

__all__ = ["crank_nicolson_residual"]


def crank_nicolson_residual(residual: Residual) -> ca.Function:
    """Build the per-interval Crank–Nicolson residual for ``residual``.

    The returned ``Function`` maps ``(x_i, x_next, e_mid, theta, t_mid,
    dt)`` to the residual ``F`` evaluated at the interval midpoint, a
    vector of length ``#equations``.
    """
    f = residual.function
    n = residual.expression.shape[0]
    n_dynamic = int(f.size_in("xdot")[0])
    n_exogenous = int(f.size_in("e")[0])
    n_parameters = int(f.size_in("theta")[0])

    x_i = ca.SX.sym("x_i", n)
    x_next = ca.SX.sym("x_next", n)
    e_mid = ca.SX.sym("e_mid", n_exogenous)
    theta = ca.SX.sym("theta", n_parameters)
    t_mid = ca.SX.sym("t_mid")
    dt = ca.SX.sym("dt")

    x_mid = 0.5 * (x_i + x_next)
    xdot = (x_next[:n_dynamic] - x_i[:n_dynamic]) / dt
    interval = f(xdot, x_mid, e_mid, theta, t_mid)

    return ca.Function(
        "cn_interval",
        [x_i, x_next, e_mid, theta, t_mid, dt],
        [interval],
        ["x_i", "x_next", "e_mid", "theta", "t_mid", "dt"],
        ["R"],
    )

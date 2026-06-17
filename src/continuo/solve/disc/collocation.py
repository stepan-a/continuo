"""General collocation discretisation of the model residual.

For the implicit DAE ``F(ẋ, x, e, θ, t) = 0`` an ``s``-stage collocation
method (:class:`~continuo.solve.disc.tableaux.ButcherTableau`) discretises
one interval ``[tᵢ, tᵢ₊₁]`` of step ``dt`` by introducing, per interval,
*stage unknowns*: the stage derivatives ``Vⱼ ∈ ℝ^{n_dyn}`` (the value of
``ẋ`` at the collocation point ``τⱼ = tᵢ + cⱼ·dt``) and the stage algebraic
values ``Wⱼ ∈ ℝ^{n_alg}``. The full stage state is

    Zⱼ = [ xᵢ^dyn + dt·Σ_l A[j,l] V_l ;  Wⱼ ]            (endogenous order)

and the per-interval residual stacks the ``s`` stage equations

    F(Vⱼ, Zⱼ, e(τⱼ), θ, τⱼ) = 0                          (s·n rows)

— whose dynamic rows are the collocation conditions and whose algebraic rows
pin ``Wⱼ`` (index-1 DAE consistency at the stages) — followed by the dynamic
node update

    xᵢ₊₁^dyn − xᵢ^dyn − dt·Σⱼ b[j] Vⱼ = 0                (n_dyn rows).

The stage-derivative form never inverts ``A``, so it handles the singular
``A`` of Lobatto IIIA uniformly with Gauss and Radau, and at one Gauss stage
reduces to the Crank–Nicolson residual. The perfect-foresight driver stacks
these per-interval residuals across the grid (with the stage unknowns), keeps
the algebraic rows pointwise at the nodes too, and adds the boundary
conditions.
"""

from __future__ import annotations

import casadi as ca

from continuo.codegen.residual import Residual
from continuo.solve.disc.tableaux import ButcherTableau

__all__ = ["collocation_residual"]


def collocation_residual(residual: Residual, tableau: ButcherTableau) -> ca.Function:
    """Build the per-interval collocation residual for ``residual`` and ``tableau``.

    The returned ``Function`` maps ``(x_i, x_next, V, W, e_stages, theta,
    t_i, dt)`` to the stacked residual of length ``s·n + n_dyn``: the ``s``
    stage residuals (each the full ``F`` at a collocation point) followed by
    the dynamic node update. ``V`` / ``W`` / ``e_stages`` are the stage
    quantities concatenated stage-major.
    """
    f = residual.function
    n = residual.expression.shape[0]
    n_dynamic = int(f.size_in("xdot")[0])
    n_exogenous = int(f.size_in("e")[0])
    n_parameters = int(f.size_in("theta")[0])
    n_algebraic = n - n_dynamic
    s = tableau.stages
    A = tableau.A
    b = tableau.b
    c = tableau.c

    x_i = ca.SX.sym("x_i", n)
    x_next = ca.SX.sym("x_next", n)
    V = ca.SX.sym("V", n_dynamic * s)
    W = ca.SX.sym("W", n_algebraic * s)
    e_stages = ca.SX.sym("e_stages", n_exogenous * s)
    theta = ca.SX.sym("theta", n_parameters)
    t_i = ca.SX.sym("t_i")
    dt = ca.SX.sym("dt")

    def stage_v(j: int) -> ca.SX:
        return V[j * n_dynamic : (j + 1) * n_dynamic]

    def stage_w(j: int) -> ca.SX:
        return W[j * n_algebraic : (j + 1) * n_algebraic]

    def stage_e(j: int) -> ca.SX:
        return e_stages[j * n_exogenous : (j + 1) * n_exogenous]

    x_i_dyn = x_i[:n_dynamic]
    stage_rows: list[ca.SX] = []
    for j in range(s):
        z_dyn = x_i_dyn + dt * sum((A[j, m] * stage_v(m) for m in range(s)), ca.SX.zeros(n_dynamic))
        z = z_dyn if n_algebraic == 0 else ca.vertcat(z_dyn, stage_w(j))
        tau = t_i + c[j] * dt
        stage_rows.append(f(stage_v(j), z, stage_e(j), theta, tau))

    update = (
        x_next[:n_dynamic]
        - x_i_dyn
        - dt * sum((b[j] * stage_v(j) for j in range(s)), ca.SX.zeros(n_dynamic))
    )

    return ca.Function(
        "coll_interval",
        [x_i, x_next, V, W, e_stages, theta, t_i, dt],
        [ca.vertcat(*stage_rows, update)],
        ["x_i", "x_next", "V", "W", "e_stages", "theta", "t_i", "dt"],
        ["R"],
    )

The ``steady_state_model`` block
================================

The ``steady_state_model;`` block gives an *analytical* steady state for
the model — one assignment per endogenous variable, expressing it as a
function of the parameters and the exogenous values:

.. code-block:: text

   steady_state_model;
     A = 1 + e/theta;
     K = (alpha*A/(rho+delta))^(1/(1-alpha));
     Y = A * K^alpha;
     C = Y - delta*K;
   end;

The left-hand side of each assignment must be the name of a declared
endogenous variable (state, jump, or algebraic). The right-hand side may
reference parameters, exogenous variables, and any endogenous variable
already assigned above it in the block.

The block must cover **every** endogenous variable; a missing assignment
raises an IR error. An ``initial_guess`` block (see :doc:`boundary`)
may be added as a Newton seed when the steady state has multiple
solutions, but it does not replace the analytical block.

Numerical fallback
------------------

When no ``steady_state_model`` block is present, the steady state is
computed numerically: a nonlinear root-find on the residual with all time
derivatives set to zero. The algorithm is **pluggable** — the default
``auto`` tries a trust-region hybrid, then least-squares, then a
continuation method — and is chosen with ``solver=`` on the ``steady``
directive, the :meth:`continuo.Model.steady_state` API, or the
``--steady-solver`` CLI flag. See :doc:`/steady_solvers` for the presets
and how ``auto`` routes.

For most non-trivial models the analytical block is still both faster and
more robust, and is what the shipped examples use.

How the steady state is used
----------------------------

The computed steady state serves three purposes:

1. As the **terminal anchor** of every jump variable in each segment:
   the solver enforces ``jump(t_end) = SS(jump)`` so that the
   continuous-time saddle path is selected.
2. As the **initial guess** for Newton (tiled across the grid).
3. As the value of the ``steady_state(var)`` callable inside ``initval``
   (see :doc:`boundary`).

The steady state used at each of those places is computed at the
exogenous values active for that segment / time, except where overridden
explicitly with ``e={…}`` (see :doc:`boundary`).

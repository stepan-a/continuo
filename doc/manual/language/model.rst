The ``model`` block
===================

The ``model;`` block lists the equations of the dynamic system. Each
equation is a continuous-time relation in the endogenous variables, the
exogenous processes, the parameters, and the reserved time ``t``.

.. code-block:: text

   model;
     diff(K) = Y - C - delta*K;                     // state equation
     diff(A) = theta*(1 - A) + e;                   // state equation
     diff(C) = C * (alpha*Y/K - delta - rho);       // jump equation (Euler)
     Y = A * K^alpha;                               // algebraic equation
   end;

Equation forms
--------------

Two forms are accepted:

Explicit
   ``LHS = RHS ;`` — interpreted as the residual ``LHS - RHS = 0``.

Bare
   ``expr ;`` — interpreted as ``expr = 0``.

Both forms produce a residual; the assembled vector
``F(ẋ, x, e, θ, t) = 0`` is what the solver discretises and stacks.

Time derivatives: ``diff``
--------------------------

The time derivative of a variable is written ``diff(x)``. Higher-order
derivatives may be written ``diff(x, k)`` (these are reduced to a chain
of first-order auxiliary states by the IR). ``diff`` is only meaningful
in the ``model`` block.

A ``var(state)`` or ``var(jump)`` must have its time derivative defined
on the left-hand side of exactly one equation; an algebraic ``var`` must
not.

Equation tags
-------------

Each equation may carry one or more comma-separated tags in square
brackets immediately before it:

.. code-block:: text

   [name='Euler']
   diff(C) = C * (alpha*Y/K - delta - rho);

Tags are stored on the equation in the IR; they have no numerical
effect (yet), but are useful labels for diagnostics and post-solve
inspection.

What ``model`` does *not* accept
---------------------------------

- The shock-path shape helpers (``step``, ``pulse``, ``ramp``, ``bump``,
  ``expdecay``, ``smoothstep``) are forbidden in ``model``. They are
  only meaningful as time-shape sugars in ``shocks`` paths; using one
  in ``model`` raises a clear ``CodegenError``.
- Strings and dict literals have no numeric meaning in a model
  expression and are rejected.

For the operators and functions allowed in equations see
:doc:`expressions`.

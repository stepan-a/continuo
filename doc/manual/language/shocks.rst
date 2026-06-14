The ``shocks`` block
====================

The ``shocks;`` block assigns each exogenous variable (``varexo``) a
**deterministic, time-dependent path**. Stochastic innovations have no
place here — Continuo solves a perfect-foresight problem, in which the
realised exogenous values are the path the agents condition on.

Basic syntax
------------

For each shock, repeat ``var <name>;`` followed by one or more ``path``
assignments. A bare ``path = …;`` is shorthand for ``path at t = 0 = …``
— "this path is the belief from ``t = 0`` onward":

.. code-block:: text

   shocks;
     var z;
     path = 1.1;                              // constant path: z(t) = 1.1
   end;

The right-hand side of ``path`` is a symbolic expression in the reserved
time ``t``, the parameters, and the shock-shape helpers (below). It is
evaluated at every grid node.

Time-dependent paths
--------------------

Any expression in ``t`` is allowed. The simplest building block is
``if(condition, then, else)``, with the comparison and logical operators
(``<``, ``<=``, ``>``, ``>=``, ``==``, ``!=``, ``&&``, ``||``, ``!``):

.. code-block:: text

   shocks;
     var z;
     path = if(t >= 5, 1.1, 1.0);                   // step at t = 5
   end;

For common shapes, the helper functions below are clearer (and the
parser sees the discontinuity locations explicitly).

Shock-shape helpers
-------------------

The following helpers are available **only inside ``shocks`` paths**
(they are rejected as a ``CodegenError`` in ``model`` equations):

============================  ===========================================
``step(t, t0)``               0 before ``t0``, 1 from ``t0`` on.
``pulse(t, t0, t1)``          1 on ``[t0, t1)``, 0 elsewhere.
``ramp(t, t0, t1)``           0 then linear 0→1 over ``[t0, t1]`` then 1.
``bump(t, t0, t1)``           Smooth (C-infinity) bump on ``(t0, t1)``,
                              peak 1 at the centre.
``expdecay(t, t0, tau)``      0 before ``t0``, then ``exp(-(t-t0)/tau)``
                              (value 1 at ``t0``).
``smoothstep(t, t0, k)``      Logistic step at ``t0`` with steepness
                              ``k`` (value 0.5 at ``t0``).
============================  ===========================================

They scale and shift like any expression:

.. code-block:: text

   shocks;
     var A;
     path = 1.0 + 0.05 * pulse(t, 8, 12);       // boom over [8, 12)

     var z;
     path = 1.0 + 0.05 * expdecay(t, 0, 3);     // exp-decaying shock
   end;

.. note::

   The shape helpers are lowered to the same CasADi expressions you
   would get by hand-writing them with ``if`` and arithmetic; their
   present role is documentary. A future release will use their
   explicit discontinuity arguments to *auto-align* the discretisation
   grid; until then, a discontinuity that falls between nodes is
   smeared by up to one ``dt``.

Multi-revelation surprises
--------------------------

Continuo supports beliefs that change over the simulation horizon, the
continuous-time analogue of MIT shocks. Each ``path at t = <reveal_time>
= <expression>`` declares that *at the reveal time, agents adopt this
expression as their belief about the entire future path of the shock*.

.. code-block:: text

   shocks;
     var u;
     path at t=0  = if(t >= 7, 0.01, 0);    // initial belief
     path at t=4  = if(t >= 7, 0.03, 0);    // surprise at t = 4
     path at t=10 = if(t >= 7, 0.025, 0);   // another surprise at t = 10
   end;

The reveal times partition ``[0, T]`` into **segments**; each segment is
solved as a complete perfect-foresight problem under the belief active
at its start, with the state carried continuously from the previous
segment and the jumps re-optimising at the reveal. Only the realised
slice ``[t_i, t_{i+1})`` of each segment's solve is kept; the agents'
counterfactual continuation beyond ``t_{i+1}`` is discarded.

Reveal times are sorted by the parser; duplicates on the same shock are
rejected, and mixing the bare ``path = …`` sugar with an explicit
``path at t = 0 = …`` on the same shock is forbidden to keep the meaning
unambiguous.

Anticipated vs unanticipated
----------------------------

A useful idiom — used in many of the shipped examples — is the contrast
between

- an **anticipated** future change, written as a single belief with the
  step inside it, so the whole horizon is one segment:

  .. code-block:: text

     shocks;
       var e;
       path = 0.05 * step(t, 10);    // known from t=0, takes effect at t=10
     end;

- an **unanticipated** change at the same time, written as two beliefs:

  .. code-block:: text

     shocks;
       var e;
       path at t=0  = 0;             // belief until the reveal
       path at t=10 = 0.05;          // learned only at t = 10
     end;

The eventual realised paths are identical; the difference is what
agents *expect*, which shows up in the jump variables (they react at
``t = 0`` under anticipation, only at ``t = 10`` under the surprise).

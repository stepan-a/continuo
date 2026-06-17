Declarations
============

Every name that appears in the model must first be declared as a
variable or a parameter.

Endogenous variables: ``var``
------------------------------

The ``var`` keyword declares one or more endogenous variables, optionally
qualified by their dynamic role:

.. code-block:: text

   var(state) K, A;          // predetermined: pinned at t=0 by initval
   var(jump)  C;             // forward-looking: pinned at t=T by terminal SS
   var        Y, r;          // unqualified = algebraic (no time derivative)

The three roles are:

``state`` (predetermined)
   Carries a time derivative — i.e. ``diff(state)`` appears on the left of
   exactly one equation in the ``model`` block — and is pinned at ``t=0``
   by an ``initval`` block.

``jump`` (forward-looking)
   Also carries a time derivative, but is *not* pinned at ``t=0``; the
   solver anchors it at the terminal steady state. This is the
   continuous-time analogue of a Dynare jumper/forward variable.

``var`` *(no qualifier)*
   Algebraic: no time derivative, defined by a static equation.

The IR classifies a variable's role from the equations as well as the
declaration, and rejects inconsistencies (e.g. a ``var(state)`` with no
``diff(.)`` on a left-hand side, or two ``diff(x)`` definitions).

The qualifier may also carry a **domain constraint** (``positive`` /
``negative`` / ``boundaries=(lo, hi)``) that keeps the variable strictly
inside a known range when the steady state is solved numerically — see
:doc:`constraints`.

Exogenous processes: ``varexo``
-------------------------------

``varexo`` declares one or more exogenous (forcing) variables — the names
that appear on the right of ``var X; path = …;`` in the ``shocks`` block:

.. code-block:: text

   varexo e, delta;

Inside the ``model`` block, a ``varexo`` is read like any other name; the
solver provides its time-varying value at each grid point from the active
shock path. See :doc:`shocks` for the path syntax.

Parameters: ``parameters`` and assignments
------------------------------------------

``parameters`` declares the names; values are assigned afterwards by
ordinary ``name = expression;`` statements:

.. code-block:: text

   parameters alpha, delta, rho;
   alpha = 0.33;
   delta = 0.10;
   rho   = 0.05;

Parameter values may reference previously-assigned parameters and any
literal expression that the model language accepts (arithmetic, ``exp``,
``log``, ``sqrt``, …). They are resolved once at solve time.

Reserved names
--------------

The identifier ``t`` is reserved: inside the ``shocks`` block it stands
for the (continuous) time variable, and inside ``model`` and
``steady_state_model`` blocks it is the time argument at which the
expression is evaluated. ``diff`` and ``if`` are reserved as built-in
functions; ``steady_state`` is reserved as the steady-state callable.
The shock-shape helpers (``step``, ``pulse``, ``ramp``, ``bump``,
``expdecay``, ``smoothstep``) are reserved inside ``shocks`` blocks only.

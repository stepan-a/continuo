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
   Carries a time derivative — i.e. ``diff(state)`` appears in exactly one
   equation of the ``model`` block — and is pinned at ``t=0`` by an
   ``initval`` block.

``jump`` (forward-looking)
   Also carries a time derivative, but is *not* pinned at ``t=0``; the
   solver anchors it at the terminal steady state. This is the
   continuous-time analogue of a Dynare jumper/forward variable.

``var`` *(no qualifier)*
   Algebraic: no time derivative, defined by a static equation.

The role is *declared*, not inferred: the IR validates each declared role
against how the variable is used in the equations and rejects inconsistencies
(e.g. a ``var(state)`` whose ``diff(.)`` never appears, or a variable both
differentiated and pinned by a static equation).

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

Special names
-------------

A few identifiers carry a built-in meaning and should not be reused as
variable names. (The grammar does not reserve them — they tokenise as ordinary
identifiers — but each is special-cased downstream, so using one as a declared
name is unsupported.) ``t`` is the (continuous) time variable: inside the
``shocks`` block, and inside ``model`` and ``steady_state_model`` blocks the
time argument at which the expression is evaluated. ``diff`` and ``if`` are
built-in functions; ``steady_state`` is the steady-state callable. The
shock-shape helpers (``step``, ``pulse``, ``ramp``, ``bump``, ``expdecay``,
``smoothstep``) are built-in inside ``shocks`` blocks only.

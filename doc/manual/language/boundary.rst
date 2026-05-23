Initial conditions: ``initval`` and ``initial_guess``
======================================================

``initval``
-----------

The ``initval;`` block pins the **state** variables at ``t = 0``. Jumps
and algebraic variables must not appear here — they are determined by
the equations and the terminal steady state.

Explicit form
^^^^^^^^^^^^^

Each state has an explicit right-hand side, a numeric expression in
parameters (and optionally ``steady_state(...)`` calls — see below):

.. code-block:: text

   initval;
     K = 0.8 * steady_state(K);   // 20% below the steady state
     A = 1.05;                    // a 5% productivity displacement
   end;

The right-hand side is evaluated once at solve time. If a higher-order
state was reduced to auxiliary first-order states, its derivative is
pinned by writing ``diff(x)`` on the left:

.. code-block:: text

   initval;
     x = 0;
     diff(x) = 1;        // pins the first auxiliary state of x
   end;

``initval(steady)`` sugar
^^^^^^^^^^^^^^^^^^^^^^^^^

``initval(steady);`` fills every state from the **initial steady
state** automatically — equivalent to writing ``state =
steady_state(state)`` for every state. Auxiliary derivative states get
``0`` (their value in steady state).

.. code-block:: text

   initval(steady);   // no body needed when this is the whole anchor
   end;

Mix explicit and sugar by listing some states explicitly: those listed
take their explicit value, the rest are auto-filled from the steady
state.

The ``e={…}`` exogenous override
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``initval(steady, e={var: value, …})`` is the idiom for a permanent
change *already in effect* at ``t = 0``: it anchors the initial state at
the steady state evaluated at the *overridden* exogenous values, while
the path itself runs under the active (post-change) values.

.. code-block:: text

   // a permanent rise in e from 0 to 0.05 at t=0; anchor at the old SS
   initval(steady, e={e: 0});
   end;

   shocks;
     var e; path = 0.05;
   end;

The override merges with the active exogenous values: keys present in
the dictionary override, the rest are taken from the active configuration.
Override keys are validated against the declared ``varexo``; an unknown
name raises a ``SolveError``.

The ``steady_state(var, e={…})`` callable
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The same override is available on the per-variable callable, for use
inside a plain ``initval`` block:

.. code-block:: text

   initval;
     K = steady_state(K, e={e: 0});      // K at the e=0 SS
     A = 1;                              // explicit override of A
   end;

Without an ``e=`` argument, ``steady_state(var)`` resolves to the
*initial* steady state (computed at the active exogenous values).

.. note::

   At the moment the ``steady_state(var, …)`` callable inside
   ``initval`` honours only the ``e={…}`` keyword. Other keywords (such
   as ``t=``) are reserved by the spec but not yet wired through the
   solver and will raise a clear ``SolveError`` if used.

``initial_guess``
-----------------

A separate optional block, ``initial_guess;``, provides a starting
iterate for the nonlinear solver. Any endogenous variable (state, jump
or algebraic) may appear; the block need not be complete.

.. code-block:: text

   initial_guess;
     C = 1.2;
     q = 1.1;
   end;

``initial_guess`` does not pin any variable — it just seeds Newton.
The terminal-steady-state guess is used by default; supply
``initial_guess`` when that guess is poor (e.g. far from the saddle
path, or near multiple steady states).

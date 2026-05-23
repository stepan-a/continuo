Quick start
===========

A first model
-------------

The smallest non-trivial continuous-time saddle: a stable state ``x`` (a
decaying transition from an initial condition) and an unstable jump
``y`` (anchored at its terminal steady state of zero):

.. code-block:: text

   var(state) x;
   var(jump)  y;

   model;
     diff(x) = -x;
     diff(y) = y;
   end;

   initval;
     x = 1;
   end;

   simulate(T=5, N=20);

Save it as ``saddle.mod``. The model has one **state** (predetermined,
pinned by ``initval``) and one **jump** (forward-looking, pinned at the
terminal steady state by the solver). The ``model;`` block lists the
equations; ``simulate(...)`` requests a perfect-foresight solve over
``[0, 5]`` discretised on a 20-interval grid.

From the command line
---------------------

.. code-block:: console

   $ continuo saddle.mod
   continuo: wrote 21 rows to saddle.csv

This writes one row per grid point (header ``t, x, y``) into
``saddle.csv``. Override the horizon, grid resolution, or output path:

.. code-block:: console

   $ continuo saddle.mod -T 10 -N 100 -o /tmp/saddle.csv

See :doc:`cli` for the full CLI reference.

From Python
-----------

.. code-block:: python

   import continuo

   model = continuo.parse("saddle.mod")
   sol = model.simul()                 # uses T, N from the simulate command
   print(sol["x"][0], sol["x"][-1])    # 1.0, ~0.0067

   ss = model.steady_state()           # the trivial steady state x=y=0

The :class:`~continuo.Model` returned by :func:`~continuo.parse` exposes
the parsed model and its solvers; :class:`~continuo.Solution` is the
result of :meth:`~continuo.Model.simul`, with NumPy arrays for the time
grid and the solved path. See :doc:`api` for the full reference.

A richer example
----------------

The shipped Ramsey/RBC model in ``examples/rbc/`` is the natural next
step. It illustrates:

- two state variables (capital ``K`` and productivity ``A``),
- a jump (consumption ``C``) and an algebraic variable (output ``Y``),
- an analytical ``steady_state_model`` block,
- shock paths and surprises in the ``shocks`` block,
- factoring the shared model out of multiple scenarios with the
  macroprocessor (``@#include "common.mod"``).

See :doc:`examples` for the full list of worked-out models, and
:doc:`language/index` for the reference on each construct used.

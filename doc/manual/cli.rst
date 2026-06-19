Command-line interface
======================

The ``continuo`` console script is a thin wrapper over the Python API:
it parses a ``.mod`` file, runs the simulation, and writes the solved
path to a CSV.

Synopsis
--------

.. code-block:: console

   continuo MODEL.mod [-o OUTPUT.csv] [-T HORIZON] [-N INTERVALS]
            [--scheme SCHEME] [--order ORDER] [--adapt TOL] [--monitor MONITOR]
            [--solver SOLVER] [--steady-solver SOLVER]
            [--steady-solver-option KEY=VALUE]

Positional argument
-------------------

``MODEL.mod``
   Path to the ``.mod`` file to solve. The file must contain a
   ``simulate`` command (or supply ``-T``/``-N`` to fill in the missing
   pieces).

Options
-------

``-o OUTPUT.csv``, ``--output OUTPUT.csv``
   Path of the CSV file to write. Defaults to ``MODEL.csv`` (same
   directory and stem as the input).

``-T HORIZON``, ``--horizon HORIZON``
   Override the simulation horizon ``T`` from the ``simulate`` command.
   Float, positive.

``-N INTERVALS``, ``--intervals INTERVALS``
   Override the grid resolution ``N``. Integer, positive.

``--scheme SCHEME``
   Override the discretisation scheme from the ``simulate`` command —
   ``crank_nicolson`` (default), ``gauss``, ``radau`` or ``lobatto_iiia``.
   See :doc:`schemes`.

``--order ORDER``
   Collocation order for a multi-stage ``--scheme`` (integer; the family
   default when omitted; not accepted for ``crank_nicolson``).

``--adapt TOL``
   Turn on adaptive mesh refinement to the error tolerance ``TOL`` (float);
   ``N`` becomes the starting resolution. See :doc:`grids`.

``--monitor MONITOR``
   The error monitor driving ``--adapt`` — ``residual`` (default) or
   ``richardson``. Requires ``--adapt``. See :doc:`grids`.

``--solver SOLVER``
   Choose the linear backend, overriding the ``simulate`` directive —
   ``auto`` (default), ``superlu``, ``klu``, ``klu-nobtf``, ``umfpack``
   or ``pardiso``. An unavailable backend is reported as a clean error.
   See :doc:`solvers`.

``--steady-solver SOLVER``
   Choose the nonlinear steady-state algorithm, overriding the ``steady``
   directive — ``auto`` (default), ``newton``, ``hybr``, ``lm``,
   ``kinsol``, ``homotopy``, ``broyden``, ``krylov``, ``df-sane`` or
   ``anderson``. See :doc:`steady_solvers`.

``--steady-solver-option KEY=VALUE``
   Set a backend-specific option for the steady solver; repeatable, e.g.
   ``--steady-solver-option strategy=picard``. Requires a named
   ``--steady-solver`` (the default ``auto`` rejects options). Numeric
   values are coerced. See :doc:`steady_solvers`.

Output format
-------------

The CSV has one row per grid point. The first column is the time
``t``; subsequent columns are the endogenous variables in declaration
order, with the header line giving their names:

.. code-block:: text

   t,K,A,C,Y
   0.0,4.0163,1.05,1.1898,1.6613
   0.2,4.0295,1.0452,1.1912,1.6556
   ...
   50.0,4.0167,1.0,1.1806,1.5823

Exit status
-----------

``0``
   Success.

``1``
   A user-facing error: the input file cannot be read, the output CSV cannot
   be written, or the macroprocessor / parser / IR / codegen / solver
   rejected it (a missing ``simulate`` command with no ``-T`` / ``-N``
   override surfaces as a solver error). The message is written to
   ``stderr``, prefixed with ``continuo:``.

Anything else is a bug.

Examples
--------

.. code-block:: console

   $ continuo rbc.mod                        # writes rbc.csv
   continuo: wrote 251 rows to rbc.csv

   $ continuo rbc.mod -T 100 -N 500          # longer horizon, finer grid
   continuo: wrote 501 rows to rbc.csv

   $ continuo rbc.mod -o /tmp/out.csv        # explicit output path
   continuo: wrote 251 rows to /tmp/out.csv

Programmatic equivalent
-----------------------

The CLI is implemented in :mod:`continuo.cli` and is exactly
equivalent to:

.. code-block:: python

   import continuo

   model = continuo.parse("MODEL.mod")
   sol = model.simul(horizon=T, intervals=N)   # T, N optional overrides
   # write sol.t and sol.path to CSV ...

See :doc:`api` for the Python interface.

Command-line interface
======================

The ``continuo`` console script is a thin wrapper over the Python API:
it parses a ``.mod`` file, runs the simulation, and writes the solved
path to a CSV.

Synopsis
--------

.. code-block:: console

   continuo MODEL.mod [-o OUTPUT.csv] [-T HORIZON] [-N INTERVALS]

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
   A user-facing error: the file cannot be read, the macroprocessor /
   parser / IR / codegen / solver rejected it, or the file has no
   ``simulate`` command and neither ``-T`` nor ``-N`` were supplied. The error
   message is written to ``stderr`` and is prefixed with ``continuo:``.

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

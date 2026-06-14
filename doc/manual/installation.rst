Installation
============

Requirements
------------

Continuo targets Python 3.13 and above. Its runtime dependencies are:

- `CasADi <https://web.casadi.org/>`_ ≥ 3.6 (symbolic engine and AD),
- NumPy ≥ 1.26,
- SciPy ≥ 1.11 (sparse linear algebra),
- `Lark <https://lark-parser.readthedocs.io/>`_ ≥ 1.1 (parser generator).

From a clone
------------

The recommended way during development is an editable install from the
repository root:

.. code-block:: console

   $ git clone https://git.ithaca.fr/stepan/continuo.git
   $ cd continuo
   $ pip install -e .

That installs the ``continuo`` Python package and the ``continuo``
command-line entry point.

Optional extras
---------------

The ``Solution`` object can be converted to a pandas ``DataFrame`` or an
xarray ``Dataset``; those conversions require the optional extras:

.. code-block:: console

   $ pip install -e ".[pandas,xarray]"

To build this manual locally:

.. code-block:: console

   $ pip install sphinx furo sphinx-copybutton
   $ cd doc/manual && make html
   $ xdg-open _build/html/index.html

Verifying the install
---------------------

A working install runs the test suite cleanly:

.. code-block:: console

   $ pip install -e ".[dev]"
   $ pytest -q

and the CLI executes the smallest model:

.. code-block:: console

   $ cat > saddle.mod <<'EOF'
   var(state) x;
   var(jump) y;
   model;
     diff(x) = -x;
     diff(y) = y;
   end;
   initval; x = 1; end;
   simulate(T=5, N=20);
   EOF
   $ continuo saddle.mod
   continuo: wrote 21 rows to saddle.csv

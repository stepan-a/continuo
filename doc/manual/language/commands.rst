Commands
========

A ``.mod`` file ends with one or more commands that drive the solver.

``simulate``
------------

.. code-block:: text

   simulate(T = 50, N = 250);

Solves the model on ``[0, T]`` discretised on ``N`` equal intervals
(``N + 1`` grid points). The result is returned by the Python API
(:meth:`continuo.Model.simul`) as a :class:`~continuo.Solution`, or
written to CSV by the CLI.

Arguments (all keyword):

``T`` (required, ``float``)
   The simulation horizon. Positive.

``N`` (required, ``int``)
   The number of grid intervals. Positive.

``scheme`` (optional, string, default ``"crank_nicolson"``)
   The discretisation scheme. Currently only ``crank_nicolson``
   (implicit midpoint, second-order, A-stable) is implemented; other
   names parse but raise a ``SolveError`` at solve time.

``solver`` (optional, preset name, default ``auto``)
   The linear backend for the Newton solve — ``auto``, ``superlu``,
   ``klu``, ``umfpack`` or ``pardiso``. Write the dashed preset as a
   string: ``solver = "klu-nobtf"``. Unknown names are rejected when the
   command is validated; whether a named backend is actually available is
   decided at solve time. An explicit ``solver=`` argument on the API or
   CLI overrides this directive. See :doc:`/solvers`.

A file may contain at most one ``simulate`` command. The Python API
and the CLI both allow overriding ``T`` and ``N`` at the call site:

.. code-block:: python

   model.simul(horizon=100.0, intervals=500)

.. code-block:: console

   $ continuo model.mod -T 100 -N 500

``steady``
----------

The ``steady`` command requests a *diagnostic* steady-state evaluation
— it does not write a path, only reports the steady state at a
specified time (or for a specified exogenous configuration).

.. code-block:: text

   steady;                          // SS at t = T (the terminal SS)
   steady(t = 5);                   // SS at t = 5 under the active exogenous
   steady(t = 0, e = {delta: 0.05});// SS at t = 0 with an explicit override

Arguments (all keyword, all optional):

``t`` (``float``)
   The time at which to evaluate the steady state. Defaults to the
   simulation horizon. Must be in ``[0, T]``.

``e`` (mapping ``{varexo: value, …}``)
   Exogenous override. Each key must be a declared ``varexo``.

The Python API exposes the same calculation through
:meth:`continuo.Model.steady_state`.

.. note::

   The general ``steady_state(var, t=…, e={…})`` callable inside
   *model* equations (the segment-aware terminal-SS reference described
   in the design spec) is not yet implemented. Inside ``initval``,
   ``steady_state(var)`` and ``steady_state(var, e={…})`` are honoured;
   see :doc:`boundary`.

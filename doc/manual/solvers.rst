Linear solvers
==============

Every Newton step of the perfect-foresight solve reduces to one sparse
linear system, :math:`J\,\Delta X = -G`, where :math:`J` is the Jacobian
of the stacked collocation residual. That linear core is **pluggable**:
continuo ships several backends and chooses one automatically, but you can
pin a specific backend from the API, the ``simulate`` directive, or the
command line.

The pattern of :math:`J` is constant across Newton iterations — and, at a
fixed grid, across the segments of a multi-segment run — so the backends
that can separate the *symbolic* analysis (fill-reducing ordering, block
structure) from the *numeric* factorisation analyse the pattern **once**
and refresh only the numbers thereafter. continuo exploits this: the
analysis is hoisted out of the Newton loop and reused across segments, and
each segment warm-starts its first step from the previous factorisation.

Choosing a backend
-------------------

Three entry points, from the most global to the most local — later ones
override earlier ones (**CLI > directive > default**):

Python API
   Pass ``solver=`` to :meth:`continuo.Model.simul` (or to
   ``continuo.solve_pf``):

   .. code-block:: python

      model.simul(solver="klu")
      model.simul(solver="auto")          # the default

The ``simulate`` directive
   Pin the backend with the model (see :doc:`language/commands`):

   .. code-block:: text

      simulate(T = 50, N = 250, solver = klu);

Command line
   Override the directive at the call site:

   .. code-block:: console

      $ continuo model.mod --solver klu

The value is a **preset name** (below), or — from the Python API only — a
constructed solver instance for fine control (see `Fine control`_). The
default, ``auto``, picks a backend from the scheme's coupling structure.

Presets
-------

.. list-table::
   :header-rows: 1
   :widths: 18 26 30 26

   * - Preset
     - Dependency
     - Exploits
     - Default?
   * - ``superlu``
     - SciPy (always present)
     - sparsity (COLAMD)
     - fallback
   * - ``klu``
     - ``libklu.so`` (SuiteSparse)
     - block-triangular form (BTF)
     - **yes** (one-step schemes)
   * - ``klu-nobtf``
     - ``libklu.so`` (SuiteSparse)
     - sparsity (no BTF)
     - no
   * - ``umfpack``
     - ``scikit-umfpack`` extra
     - sparsity
     - no
   * - ``pardiso``
     - ``pypardiso`` extra (MKL)
     - sparsity, multithreading
     - no

A preset is only offered when its backend can actually run: ``superlu`` is
always available (SciPy is a hard dependency); ``klu`` requires
``libklu.so`` at run time; ``umfpack`` and ``pardiso`` require their
optional packages. Naming an unavailable preset raises a ``SolveError``.

``auto`` routing
----------------

``auto`` (the default) routes by the discretisation scheme's *coupling
stencil*:

- **one-step** schemes (Crank–Nicolson — the only scheme implemented
  today) produce a block-triangular stacked Jacobian, which KLU's BTF
  pre-ordering solves by block back-substitution. ``auto`` picks ``klu``
  when it is available, and falls back to ``superlu`` otherwise (warning
  once).

So out of the box, a run uses KLU when ``libklu.so`` is installed and
SuperLU otherwise — with no change in results, only in speed.

The backends
------------

``superlu`` — the robust fallback
   SciPy's SuperLU (:func:`scipy.sparse.linalg.splu`). Always present, so
   it guarantees the solver works even with no external library. Used as
   the validation reference and the last-resort fallback.

``klu`` — the recommended one-step backend
   A ``ctypes`` wrapper over SuiteSparse KLU. KLU pre-orders the matrix
   into block triangular form and reuses that symbolic analysis across
   numeric refactorisations, so the one-step stacked Jacobian is solved by
   block back-substitution. ``klu-nobtf`` turns the BTF off, leaving a
   plain sparse LU — useful where BTF is pure overhead. ``libklu.so`` is a
   system library, not a pip package; install it with Debian's
   ``libsuitesparse-dev`` (or conda's ``suitesparse``). When it is absent,
   continuo falls back to SuperLU automatically.

``umfpack`` — optional, for completeness
   SuiteSparse UMFPACK via ``scikit-umfpack``. It separates the symbolic
   and numeric phases cleanly and reports a condition estimate, but its
   numeric phase is slower than SuperLU/KLU, so it tends only to match
   SuperLU in practice. Install with the ``umfpack`` extra.

``pardiso`` — optional, for large / multi-core runs
   Intel MKL PARDISO via ``pypardiso`` — multithreaded and competitive on
   large problems, but its analysis is expensive and it has no BTF, so it
   is best for big models or long simulations rather than the small
   systems continuo usually produces. Install with the ``pardiso`` extra
   (pulls in MKL). Install both optional backends with ``solvers``.

See :doc:`installation` for the extras.

Fine control
------------

From the Python API, ``solver=`` also accepts a constructed
``LinearSolver`` instance, which lets you set backend-specific options
that the presets fix. For KLU these include ``btf`` (the BTF on/off switch
the ``klu`` / ``klu-nobtf`` presets toggle) and ``ordering`` (the
per-block fill-reducing ordering, ``"amd"`` or ``"colamd"``):

.. code-block:: python

   from continuo.solve import KluSolver

   model.simul(solver=KluSolver(btf=False, ordering="colamd"))

Guard-rails
-----------

- **Conditioning.** Backends that report a reciprocal-condition estimate
  feed a guard-rail: once a reused factorisation degrades, the driver
  falls back to a full re-factorisation (a re-pivot).
- **Stale pivots.** If a cheap refactorisation fails outright (e.g. a KLU
  zero pivot), the driver redoes a full factorisation and records the
  event.
- **Structural singularity.** KLU reports the structural rank at analysis
  time, so a structurally singular Jacobian is flagged with a clear
  ``SolveError`` rather than producing garbage.

Diagnostics
-----------

Each run records what the linear solver did in ``Solution.diagnostics``
(see :doc:`api`): the backend used, the counts of full factorisations
versus cheap refactorisations, the number of re-pivot fallbacks, the
worst reciprocal-condition estimate over the run, and the factorisation
fill. These make the cross-segment warm-start observable (a two-segment
surprise shows one factorisation and one refactorisation) and surface a
loss of conditioning before it becomes a failure.

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
override earlier ones (**argument > directive > default**, where the
``solver=`` argument is passed via the Python API or the CLI):

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
     - reused symbolic factorisation; BTF
     - **yes** (one-step schemes)
   * - ``klu-nobtf``
     - ``libklu.so`` (SuiteSparse)
     - reused symbolic factorisation (no BTF)
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

- **one-step** schemes (Crank–Nicolson and the collocation families —
  Gauss–Legendre, Radau IIA, Lobatto IIIA, each coupling only an interval's
  endpoints and its own stages) are solved fastest by ``klu``: it amortises
  the symbolic factorisation across Newton steps (and segments), which
  dominates the per-iteration cost. ``auto`` picks ``klu`` when it is
  available, and falls back to ``superlu`` otherwise (warning once).

So out of the box, a run uses KLU when ``libklu.so`` is installed and
SuperLU otherwise — with no change in results, only in speed.

The backends
------------

``superlu`` — the robust fallback
   SciPy's SuperLU (:func:`scipy.sparse.linalg.splu`). Always present, so
   it guarantees the solver works even with no external library. Used as
   the validation reference and the last-resort fallback.

``klu`` — the recommended one-step backend
   A ``ctypes`` wrapper over SuiteSparse KLU. KLU separates the symbolic
   analysis from the numeric factorisation and reuses it across
   refactorisations, so each Newton step is a cheap ``refactor`` rather
   than a full factorisation — the main reason it is ~4–7× faster than
   SuperLU here (see the benchmarks below). It also pre-orders into block
   triangular form (BTF),
   which on these models only peels the algebraic and boundary rows as
   1×1 blocks (the dynamic states/jumps couple forward and backward into
   one large irreducible block), so BTF is a secondary, sometimes neutral,
   refinement; ``klu-nobtf`` turns it off. ``libklu.so`` is a system
   library, not a pip package; install it with Debian's
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

   .. note::

      On the small systems here PARDISO is far slower than KLU (see the
      benchmarks below), and that is **not** mainly an AMD-vs-Intel MKL
      effect: forcing ``MKL_ENABLE_INSTRUCTIONS=AVX512`` gives no consistent
      speed-up, whereas ``MKL_NUM_THREADS=1`` roughly *halves* the time —
      MKL oversubscribes threads on a problem far too small to parallelise,
      and even single-threaded it stays an order of magnitude behind KLU.
      Reserve PARDISO for large models, and cap ``MKL_NUM_THREADS`` when the
      systems are small.

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
fill. These make the cross-segment warm-start observable (later segments
refactor from the first segment's factorisation rather than re-analysing) and
surface a loss of conditioning before it becomes a failure.

Benchmarks
----------

The tables below compare the available backends across the example models
(end-to-end ``Model.simul()`` wall-clock and peak resident memory).
Regenerate them with ``python examples/benchmark_solvers.py --write``. The
PARDISO figures are at MKL's default threading; on these small systems that
oversubscribes and inflates its numbers (see the note above).

.. BENCHMARK START

.. list-table:: Wall-clock per solve (median, ms)
   :header-rows: 1

   * - Model
     - n
     - superlu
     - klu
     - klu-nobtf
     - umfpack
     - pardiso
   * - cagan
     - 201
     - 17.7
     - 17.0
     - 23.5
     - 16.7
     - 337.5
   * - dornbusch
     - 903
     - 23.2
     - 23.6
     - 24.7
     - 24.2
     - 259.2
   * - goodwin
     - 4802
     - 136.0
     - 134.5
     - 131.8
     - 139.2
     - 389.5
   * - nk
     - 1503
     - 81.3
     - 80.2
     - 87.8
     - 78.9
     - 314.9
   * - nk-nonlinear
     - 3005
     - 123.1
     - 118.6
     - 120.7
     - 121.9
     - 365.0
   * - rbc
     - 1004
     - 29.7
     - 28.2
     - 30.0
     - 28.1
     - 274.4
   * - solow
     - 602
     - 26.8
     - 26.7
     - 25.5
     - 26.3
     - 260.1
   * - tobinq
     - 903
     - 31.9
     - 30.1
     - 30.6
     - 30.4
     - 263.8

.. list-table:: Peak resident memory (MiB)
   :header-rows: 1

   * - Model
     - n
     - superlu
     - klu
     - klu-nobtf
     - umfpack
     - pardiso
   * - cagan
     - 201
     - 81
     - 79
     - 79
     - 79
     - 119
   * - dornbusch
     - 903
     - 82
     - 80
     - 80
     - 82
     - 124
   * - goodwin
     - 4802
     - 96
     - 92
     - 92
     - 95
     - 151
   * - nk
     - 1503
     - 84
     - 81
     - 82
     - 83
     - 129
   * - nk-nonlinear
     - 3005
     - 91
     - 88
     - 88
     - 90
     - 141
   * - rbc
     - 1004
     - 83
     - 82
     - 81
     - 82
     - 126
   * - solow
     - 602
     - 81
     - 80
     - 80
     - 81
     - 121
   * - tobinq
     - 903
     - 83
     - 82
     - 81
     - 83
     - 124

Median of 5 runs of end-to-end ``Model.simul()`` (includes the CasADi build). Wall-clock in milliseconds; peak resident memory in MiB (whole process — the Python/CasADi/SciPy baseline dominates, and PARDISO loads MKL). Measured 2026-06-15 on AMD Ryzen AI 9 HX 370 w/ Radeon 890M, 24 cores, Python 3.13.12.

.. BENCHMARK END

Isolated linear solve
~~~~~~~~~~~~~~~~~~~~~~~

End-to-end timings are diluted by the (solver-independent) CasADi build and
evaluation. The tables below isolate the **linear solve** on each model's
real stacked Jacobian: ``factor + solve`` (a cold Newton step, factorising
from scratch) and ``refactor + solve`` (the warm per-iteration cost, reusing
the symbolic analysis and pivot order — what dominates a Newton solve once
the analysis is amortised). This warm refactor is where KLU pulls ahead: it
reuses the factorisation continuo analysed once, whereas SuperLU re-factorises
in full. Regenerate with ``python examples/benchmark_solvers.py --micro --write``.

.. MICROBENCH START

.. list-table:: factor + solve — cold, per Newton step (µs)
   :header-rows: 1

   * - Model
     - n
     - superlu
     - klu
     - klu-nobtf
     - umfpack
     - pardiso
   * - cagan
     - 201
     - 58.1
     - 13.9
     - 20.8
     - 18.0
     - 366.0
   * - dornbusch
     - 903
     - 158.9
     - 67.3
     - 151.0
     - 324.3
     - 1701
   * - goodwin
     - 4802
     - 843.8
     - 338.5
     - 190.7
     - 1265
     - 2952
   * - nk
     - 1503
     - 275.5
     - 109.9
     - 181.5
     - 429.9
     - 2704
   * - nk-nonlinear
     - 3005
     - 510.3
     - 164.0
     - 503.2
     - 909.2
     - 2136
   * - rbc
     - 1004
     - 256.5
     - 73.7
     - 160.1
     - 272.2
     - 1418
   * - solow
     - 602
     - 171.8
     - 51.6
     - 37.4
     - 231.3
     - 702.9
   * - tobinq
     - 903
     - 134.8
     - 60.0
     - 58.7
     - 182.8
     - 657.1

.. list-table:: refactor + solve — warm, amortised analysis (µs)
   :header-rows: 1

   * - Model
     - n
     - superlu
     - klu
     - klu-nobtf
     - umfpack
     - pardiso
   * - cagan
     - 201
     - 57.2
     - 14.8
     - 14.7
     - 17.7
     - 359.6
   * - dornbusch
     - 903
     - 158.6
     - 34.4
     - 52.2
     - 318.1
     - 1359
   * - goodwin
     - 4802
     - 829.5
     - 107.3
     - 98.3
     - 1272
     - 2991
   * - nk
     - 1503
     - 268.8
     - 41.6
     - 44.9
     - 428.8
     - 2383
   * - nk-nonlinear
     - 3005
     - 463.4
     - 61.5
     - 121.0
     - 908.6
     - 3038
   * - rbc
     - 1004
     - 280.8
     - 39.3
     - 47.9
     - 272.2
     - 1386
   * - solow
     - 602
     - 116.2
     - 19.9
     - 18.5
     - 231.5
     - 541.8
   * - tobinq
     - 903
     - 135.3
     - 33.6
     - 25.7
     - 183.1
     - 662.5

Median of 100 repetitions, timing only the linear-solve phases on each model's real stacked Jacobian (the CasADi build is excluded). ``refactor + solve`` is the dominant per-iteration cost once the analysis is amortised. Measured 2026-06-15 on AMD Ryzen AI 9 HX 370 w/ Radeon 890M, 24 cores, Python 3.13.12.

.. MICROBENCH END

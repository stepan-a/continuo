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
   than a full factorisation — the main reason it is ~4–10× faster than
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
     - 18.2
     - 18.4
     - 19.7
     - 18.3
     - 261.0
   * - dornbusch
     - 903
     - 23.3
     - 23.8
     - 23.4
     - 23.6
     - 261.1
   * - goodwin
     - 4802
     - 133.8
     - 122.6
     - 122.3
     - 133.0
     - 375.2
   * - nk
     - 1503
     - 79.5
     - 82.5
     - 79.8
     - 79.2
     - 318.0
   * - nk-nonlinear
     - 3005
     - 113.1
     - 109.6
     - 113.1
     - 113.4
     - 360.6
   * - rbc
     - 1004
     - 28.0
     - 26.0
     - 27.0
     - 26.2
     - 255.2
   * - solow
     - 602
     - 25.7
     - 24.2
     - 25.5
     - 25.4
     - 268.0
   * - tobinq
     - 903
     - 28.2
     - 28.3
     - 27.8
     - 28.4
     - 273.1

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
     - 102
     - 100
     - 100
     - 101
     - 139
   * - dornbusch
     - 903
     - 103
     - 101
     - 101
     - 102
     - 142
   * - goodwin
     - 4802
     - 116
     - 113
     - 112
     - 114
     - 169
   * - nk
     - 1503
     - 105
     - 102
     - 103
     - 104
     - 146
   * - nk-nonlinear
     - 3005
     - 112
     - 108
     - 109
     - 110
     - 158
   * - rbc
     - 1004
     - 105
     - 103
     - 102
     - 103
     - 144
   * - solow
     - 602
     - 103
     - 101
     - 101
     - 101
     - 141
   * - tobinq
     - 903
     - 105
     - 102
     - 103
     - 103
     - 142

Median of 5 runs of end-to-end ``Model.simul()`` (includes the CasADi build). Wall-clock in milliseconds; peak resident memory in MiB (whole process — the Python/CasADi/SciPy baseline dominates, and PARDISO loads MKL). Measured 2026-06-19 on AMD Ryzen AI 9 HX 370 w/ Radeon 890M, 24 cores, Python 3.13.14.

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
     - 46.1
     - 14.2
     - 15.3
     - 19.3
     - 463.8
   * - dornbusch
     - 903
     - 159.6
     - 47.4
     - 93.2
     - 255.1
     - 1163
   * - goodwin
     - 4802
     - 854.8
     - 341.6
     - 191.4
     - 1304
     - 4063
   * - nk
     - 1503
     - 281.1
     - 109.7
     - 193.1
     - 443.1
     - 2604
   * - nk-nonlinear
     - 3005
     - 482.8
     - 164.3
     - 520.2
     - 869.2
     - 2339
   * - rbc
     - 1004
     - 329.3
     - 52.7
     - 189.4
     - 284.7
     - 1942
   * - solow
     - 602
     - 117.0
     - 52.6
     - 37.2
     - 135.4
     - 761.2
   * - tobinq
     - 903
     - 135.3
     - 41.3
     - 59.8
     - 183.7
     - 1211

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
     - 44.7
     - 11.3
     - 11.0
     - 18.5
     - 459.4
   * - dornbusch
     - 903
     - 160.4
     - 25.6
     - 31.6
     - 255.5
     - 1004
   * - goodwin
     - 4802
     - 834.9
     - 108.1
     - 98.9
     - 1299
     - 2999
   * - nk
     - 1503
     - 275.0
     - 42.2
     - 45.9
     - 447.0
     - 2583
   * - nk-nonlinear
     - 3005
     - 476.2
     - 62.4
     - 129.9
     - 868.8
     - 2051
   * - rbc
     - 1004
     - 294.5
     - 29.7
     - 47.2
     - 284.8
     - 1218
   * - solow
     - 602
     - 117.1
     - 20.4
     - 18.3
     - 136.3
     - 530.9
   * - tobinq
     - 903
     - 135.6
     - 24.8
     - 25.7
     - 184.0
     - 982.0

Median of 50 repetitions, timing only the linear-solve phases on each model's real stacked Jacobian (the CasADi build is excluded). ``refactor + solve`` is the dominant per-iteration cost once the analysis is amortised. Measured 2026-06-19 on AMD Ryzen AI 9 HX 370 w/ Radeon 890M, 24 cores, Python 3.13.14.

.. MICROBENCH END

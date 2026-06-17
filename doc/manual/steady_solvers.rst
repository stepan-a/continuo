Steady-state solvers
====================

When a model carries no ``steady_state_model`` block, continuo finds the
steady state by solving the *algebraic* system

.. math::

   g(x) = F(0, x, e, \theta) = 0,

the model with every time derivative set to zero. This nonlinear
root-find is **pluggable**: continuo ships several algorithms and picks one
automatically, but you can pin a specific one from the API, the ``steady``
directive, or the command line.

This is a different problem from the *linear* solve documented in
:doc:`solvers`. There the backend factorises the stacked Jacobian of one
Newton step of the perfect-foresight transition; here the backend *is* the
outer nonlinear iteration that finds the steady state. The two ``solver=``
options therefore name disjoint sets of methods, and a run can mix them
freely (e.g. ``kinsol`` for the steady state, ``klu`` for the transition).

continuo builds an **exact** Jacobian :math:`\partial g/\partial x` by
CasADi automatic differentiation, so the methods that exploit it (Newton,
the MINPACK ``hybr`` / ``lm`` families, KINSOL) are preferred; the
Jacobian-free methods are offered for completeness.

Choosing a solver
-----------------

Three entry points, from the most global to the most local — later ones
override earlier ones (**argument > directive > default**):

Python API
   Pass ``solver=`` to :meth:`continuo.Model.steady_state`, or
   ``steady_solver=`` to :meth:`continuo.Model.simul` (which governs the
   internal steady-state solves of the run):

   .. code-block:: python

      model.steady_state(solver="kinsol")
      model.simul(steady_solver="homotopy")   # used for the terminal/initial SS

The ``steady`` directive
   Pin the algorithm with the model (see :doc:`language/commands`). It
   applies to *every* steady-state solve in the run, not only the
   diagnostic ``steady`` query:

   .. code-block:: text

      steady(solver = kinsol);

Command line
   Override the directive at the call site:

   .. code-block:: console

      $ continuo model.mod --steady-solver homotopy

The value is a **preset name** (below), or — from the Python API only — a
constructed ``SteadySolver`` instance for fine control. The default,
``auto``, tries a short chain and keeps the first algorithm that
converges.

Presets
-------

.. list-table::
   :header-rows: 1
   :widths: 16 16 40 28

   * - Preset
     - Jacobian
     - Method
     - Notes
   * - ``newton``
     - exact
     - Newton + Armijo line search
     - fastest with a good guess
   * - ``hybr``
     - exact
     - MINPACK Powell hybrid (trust-region dogleg)
     - ``auto`` first try; robust
   * - ``lm``
     - exact
     - Levenberg–Marquardt (least squares)
     - ``auto`` fallback; near-singular Jacobians
   * - ``kinsol``
     - exact
     - SUNDIALS KINSOL (line-search Newton)
     - needs the CasADi plugin
   * - ``homotopy``
     - exact
     - Newton homotopy / continuation
     - rescues a poor initial guess
   * - ``broyden``
     - free
     - Broyden quasi-Newton
     - no Jacobian assembly
   * - ``krylov``
     - free
     - Newton–Krylov (GMRES)
     - large sparse systems
   * - ``df-sane``
     - free
     - spectral residual (derivative-free)
     - cheap last-ditch fallback
   * - ``anderson``
     - free
     - Anderson-accelerated fixed point
     - fixed-point-structured models

All presets but ``kinsol`` are always available — SciPy is a hard
dependency. ``kinsol`` is offered only when CasADi was built with the
SUNDIALS plugin (probed with ``casadi.has_rootfinder("kinsol")``). Naming
an unavailable or unknown preset raises a ``SolveError``.

The Jacobian-free presets (``broyden`` / ``krylov`` / ``df-sane`` /
``anderson``) target the residual norm less tightly than the exact-Jacobian
methods; on a strict tolerance they may report non-convergence even when
close, so loosen ``tol=`` when selecting them explicitly.

``auto`` routing
----------------

``auto`` (the default) tries a short chain and keeps the first algorithm
whose residual falls below tolerance:

#. ``hybr`` — MINPACK's trust-region hybrid, the robust general-purpose
   workhorse with the exact Jacobian;
#. ``lm`` — Levenberg–Marquardt, which degrades gracefully when the
   Jacobian is near-singular at the steady state;
#. ``homotopy`` — Newton continuation, which marches in from the starting
   iterate when a direct solve diverges from a poor guess.

A later member runs only when the earlier ones fail to reach tolerance, so
the chain leads with robustness and falls back to least-squares and
continuation for the harder cases. ``newton`` is a deliberately *separate*
preset — pick it explicitly for the fastest path when you have a good
initial guess.

The backends
------------

``newton`` — the fast path
   Newton's method with an Armijo backtracking line search. Each step
   solves :math:`\mathrm{jac}(x)\,\Delta = -g(x)` densely (the steady
   system is small) and backtracks until the step gives a *sufficient*
   decrease of the merit :math:`\varphi(x) = \tfrac12\lVert g(x)\rVert_2^2`
   — the Armijo condition, stricter than accepting any norm drop and so
   immune to the crawling near-zero steps that can stall. Quadratic local
   convergence from the exact CasADi Jacobian; the fastest choice when the
   guess is good, but not in the ``auto`` chain.

``hybr`` / ``lm`` — MINPACK
   :func:`scipy.optimize.root` with the analytic Jacobian. ``hybr`` is
   Powell's hybrid (a trust-region dogleg) — the robust general-purpose
   choice; ``lm`` is Levenberg–Marquardt, a least-squares formulation that
   copes with a near-singular or ill-conditioned Jacobian.

``kinsol`` — SUNDIALS
   KINSOL through CasADi's ``rootfinder``, a production-grade Newton with a
   line-search globalisation that consumes the CasADi residual directly.
   Available only when the CasADi build ships the plugin. On models whose
   residual is undefined outside a region (e.g. ``K^alpha`` needs
   ``K > 0``), give a good ``initial_guess`` so KINSOL's trial points stay
   in the domain; a guessless start can wander into ``NaN`` and fail.

``homotopy`` — continuation
   The Newton homotopy
   :math:`H(x, \lambda) = g(x) - (1 - \lambda)\,g(x_0)`, marched from
   :math:`\lambda = 0` (where the starting iterate :math:`x_0` is an exact
   root of :math:`H`) to :math:`\lambda = 1` (where :math:`H = g`), each
   step solved by an inner solver (Newton by default) warm-started from the
   previous point. Because the subtracted term is constant in :math:`x`,
   the Jacobian of :math:`H` is exactly that of :math:`g`, so the analytic
   Jacobian is reused unchanged. This is the tool for a steady state that
   diverges from a poor guess.

``broyden`` / ``krylov`` / ``df-sane`` / ``anderson`` — Jacobian-free
   The quasi-Newton, Newton–Krylov, spectral-residual and
   Anderson-accelerated families from :func:`scipy.optimize.root`. They
   avoid forming or factorising the Jacobian, which matters when it is
   large or expensive; on the small dense systems continuo usually produces
   they are offered for completeness rather than speed.

Solver options
--------------

Each backend takes options, set three ways (mirroring the solver choice
itself): an ``options`` dict in the API, an ``options={…}`` mapping on the
directive, or repeated ``--steady-solver-option KEY=VALUE`` flags on the
CLI. The options are **backend-specific** — for the SciPy presets they are
:func:`scipy.optimize.root` options, for the others they are the backend's
own parameters:

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - Preset
     - Options
   * - ``newton``
     - ``line_search_steps`` (backtracking halvings per step, default 30)
   * - ``kinsol``
     - ``strategy`` ∈ ``linesearch`` (default), ``none``, ``picard``, ``fp``
   * - ``homotopy``
     - ``steps`` (continuation increments, default 12); ``inner`` (API only)
   * - ``hybr`` / ``lm``
     - SciPy MINPACK options, e.g. ``factor``, ``maxfev``, ``xtol``, ``diag``
   * - ``broyden`` / ``krylov`` / ``df-sane`` / ``anderson``
     - SciPy ``nonlin`` options, e.g. ``line_search``, ``jac_options``, ``M``

.. code-block:: python

   model.steady_state(solver="kinsol", options={"strategy": "picard"})

.. code-block:: text

   steady(solver = kinsol, options = {strategy: "picard"});

.. code-block:: console

   $ continuo model.mod --steady-solver kinsol --steady-solver-option strategy=picard

Options require a *named* solver (``auto`` rejects them, since its chain is
heterogeneous), and an unknown option for a named backend raises a clean
``SolveError``. Directive values may be strings, numbers (kept integral
when written without a decimal point) or bare identifiers (read as
strings, so ``strategy = picard`` equals ``strategy = "picard"``).

Fine control
------------

From the Python API, ``solver=`` also accepts a constructed
``SteadySolver`` instance — equivalent to a preset plus its options, but
also able to set object-valued options the string channel cannot, such as
a homotopy's ``inner`` solver:

.. code-block:: python

   from continuo.solve import HomotopySolver, NewtonSolver

   model.steady_state(solver=HomotopySolver(inner=NewtonSolver(), steps=40))

A starting iterate still comes from the ``initial_guess`` block (or a
caller-supplied ``guess=``), falling back to ``1.0`` per variable; the
solver choice only changes how the iteration proceeds from there.

Domain constraints
------------------

When a variable is declared with a domain constraint
(``var(positive) K;`` and friends, see :doc:`language/constraints`), the
numerical path solves a **reparametrised** system: it roots
:math:`F(T(y)) = 0` in an unconstrained :math:`y`, where :math:`x = T(y)`
maps onto the open declared domain, so the residual is never evaluated at an
out-of-domain :math:`x`. This removes the ``NaN`` failure mode that the
Armijo line search of ``newton`` (and a good ``initial_guess`` for
``kinsol``) could only soften. The reparametrisation is transparent to the
solver choice — ``auto`` and every preset work unchanged in :math:`y`-space,
since CasADi differentiates the composition and hands each backend the exact
:math:`\partial F/\partial y`.

The ``nodomain`` flag on the ``steady`` directive (or
``Model.steady_state(nodomain=True)``) disables the change of variable,
solving in raw :math:`x` even when constraints are declared — for debugging
or to fall back when a solution saturates a bound.

Diagnostics
-----------

The numerical path logs, at ``INFO`` level, which algorithm converged, the
iteration count and the final residual norm — so when ``auto`` falls
through to a later member of its chain, the log records which one won. A
failed solve raises a ``SolveError`` carrying the residual norm reached and
the per-backend attempts, pointing at a looser tolerance or a better
``initial_guess``.

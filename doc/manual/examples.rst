Worked examples
===============

Eight worked-out model folders ship with the source tree under
``examples/``. Each folder is self-contained:

- a ``common.mod`` with the shared declarations, ``model`` and
  ``steady_state_model``, included via ``@#include`` by each scenario,
- one or more scenario ``.mod`` files that differ only in their
  ``initval``, ``shocks`` and ``simulate`` blocks,
- a ``run_*.py`` script that solves every scenario through the Python
  API and writes an overlaid plot,
- a ``README.md`` presenting the model, the experiments and the
  simulation results, with embedded plots.

One folder, ``examples/nk-nonlinear/``, departs from this layout: its
variants differ in the equations themselves, so they ship as
self-contained ``.mod`` files with no shared ``common.mod``.

Run any scenario with the CLI or the API exactly as in the
:doc:`quickstart`. The list below points at the headline result of
each.

Saddle-path models (one state + one jump)
-----------------------------------------

``examples/rbc/``
   Ramsey/RBC with two state variables (capital and an Ornstein–
   Uhlenbeck productivity process), one jump (consumption) and one
   algebraic (output). Showcases the multi-segment surprise machinery
   (``rbc_anticipated`` vs ``rbc_surprise``) and the ``e={…}`` anchor
   (``rbc_sustained``).

``examples/dornbusch/``
   Dornbusch (1976) exchange-rate overshooting. Sticky price (state) +
   exchange rate (jump). Shows the classic impact overshoot under an
   unanticipated monetary expansion; anticipated and gradual variants
   dampen it.

``examples/tobinq/``
   Tobin's *q* investment with convex adjustment costs. Capital (state)
   + shadow value *q* (jump) + investment (algebraic). Anticipated vs
   surprise vs unanticipated profitability shocks; *q* jumps at the
   reveal time.

Pure forward-looking models (jumps only, no state)
--------------------------------------------------

``examples/cagan/``
   Cagan model of money and prices: a single jump (the price level)
   driven by an exogenous money path. Prices LEAD anticipated money;
   the surprise variant shows prices flat until the reveal. Headline
   showcase for the shock-shape helpers (``step``, ``ramp``).

``examples/nk/``
   Continuous-time New Keynesian liquidity trap (Werning, 2011).
   Output gap and inflation (both jumps); the policy rate is
   ``max(0, …)`` — an occasionally-binding ZLB. A longer *expected*
   trap deepens today's recession (forward-looking amplification).

``examples/nk-nonlinear/``
   The **fully nonlinear** continuous-time New Keynesian model in
   levels — the nonlinear companion to ``examples/nk/`` (which carries
   the log-linearised trap). Three self-contained variants driven by the
   same TFP shock: ``baseline`` (no habits), ``external_habit``, and
   ``internal_habit`` (the last internalises habits, adding a costate —
   a state — so only this variant steps outside "jumps only"). The
   policy rate keeps the ZLB kink directly in levels. The full
   derivations — household and Rotemberg firm problems, both habit
   variants, every steady state — are in a Beamer companion:
   `nk-nonlinear.pdf <https://continuo.adjemian.eu/pdf/nk-nonlinear.pdf>`_.

Pure initial-value problems (states only, no jump)
---------------------------------------------------

``examples/solow/``
   Solow–Swan growth: one state (capital), no jump. The simplest
   example; scenarios are convergence-from-below, a permanent
   savings-rate rise, and a permanent productivity rise.

``examples/goodwin/``
   Goodwin (1967) growth cycle: a Lotka–Volterra system in two states
   (employment and the wage share). The interior fixed point is a
   *centre*, so the trajectory is a closed orbit — there is no
   terminal boundary condition (no jumps to anchor) and history alone
   pins the path. Scenarios vary the initial amplitude.

Each folder's README has the model equations, parameter values,
references, and a brief discussion of the simulated dynamics.

A few folders also ship auxiliary runners behind the figures in this manual:
``examples/goodwin/run_schemes.py`` (the scheme/order accuracy comparison of
:doc:`schemes`), ``examples/rbc/run_adapt.py`` (the adaptive-refinement run of
:doc:`grids`), and ``examples/benchmark_solvers.py`` (the linear-solver
timings of :doc:`solvers`).

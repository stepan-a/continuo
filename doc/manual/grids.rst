Time grids and adaptive refinement
==================================

The perfect-foresight transition is discretised on a time grid of ``N``
intervals over ``[0, T]``. By default the grid is **uniform**; continuo can
also place the nodes non-uniformly — automatically aligning them to shock
reveal times, and (opt-in) **adaptively refining** where the solution is
hard. This is orthogonal to the discretisation *scheme* (:doc:`schemes`) and
the linear *backend* (:doc:`solvers`): any combination works.

Shock-aligned nodes
-------------------

When a ``shocks`` block reveals a new belief at time ``t``, that reveal is a
kink in the trajectory. continuo makes the reveal time an **exact grid node**
(each belief segment's mesh is built with a node there), so the kink is
resolved cleanly rather than smeared across the nearest interval. This is
automatic and needs no configuration.

Adaptive refinement
-------------------

Transitional dynamics are often *fast early and slow late*, or sharp only in
a small part of the horizon. A uniform grid then wastes nodes on the smooth
tail and under-resolves the fast part. ``adapt`` turns on **a-posteriori mesh
refinement**: continuo solves, estimates the error, **bisects the intervals
where the solution curvature is largest** (equidistribution), and re-solves —
repeating until the estimated error falls below the tolerance (or a node /
pass cap is hit). Each belief segment is refined independently, and reveal
nodes are preserved.

.. code-block:: text

   simulate(T = 50, N = 250, adapt = 1e-6);            // refine to a 1e-6 error
   simulate(T = 50, N = 250, adapt = 1e-6, monitor = residual);

.. code-block:: python

   model.simul(adapt=1e-6)                  # from the API
   model.simul(adapt=1e-6, monitor="residual")

.. code-block:: console

   $ continuo model.mod --adapt 1e-6 --monitor residual

``N`` is then the *starting* resolution. Refinement only ever *adds* nodes, so
it is monotone and the reveal / terminal nodes stay fixed.

The error monitor
~~~~~~~~~~~~~~~~~~

``monitor`` chooses how the error is estimated for the stopping test (where to
refine is always decided by the cheap curvature indicator):

``richardson`` (default)
   Solve once more on the bisected mesh and scale the difference by the
   scheme order — a **calibrated** error magnitude, scheme-agnostic (it works
   for Crank–Nicolson too). Costs one extra solve per pass.

``residual``
   The ODE defect of a smooth interpolant of the node values — an indicator
   that needs **no extra solve**, so it is cheaper, if less precisely
   calibrated.

(The placement-only ``curvature`` monitor has no error magnitude and so cannot
drive ``adapt``.)

The grid-adequacy diagnostic
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Every solve — adaptive or not — reports an **equidistribution ratio** in
``Solution.diagnostics["equidistribution_ratio"]``: the ``max/mean`` of the
per-interval curvature. A value near ``1`` means the resolution is well
balanced; a large value means it is misallocated and a non-uniform or refined
grid would help. It is a cheap way to decide whether ``adapt`` is worth turning
on for a given model.

When it helps (and when it doesn't)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Adaptivity pays off when the solution is **smooth but localised** — a fast
transient, a region of high curvature. The :doc:`RBC example <examples>`
shows the capital transition refined from an equidistribution ratio of ~24
down to ~1.5, concentrating nodes on the fast early adjustment. At a genuine
**kink** (an occasionally-binding constraint) the curvature never smooths out,
so the refiner would chase it indefinitely; that is why refinement is capped,
and why pinning a node at the non-smoothness (as the shock machinery does for
reveals) plus raising ``N`` can be the steadier choice there.

.. note::

   Refinement re-meshes between passes, so each pass re-analyses the sparsity
   pattern of its linear system (unlike the fixed-grid run, which reuses one
   analysis across the whole horizon). The cost is bounded by the node and
   pass caps.

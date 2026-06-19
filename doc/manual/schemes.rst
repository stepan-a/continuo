Discretisation schemes
======================

continuo solves the perfect-foresight transition as a two-point boundary
value problem by **global collocation**: the trajectory is discretised on a
grid of ``N`` intervals, and every node value is stacked into one large
nonlinear system solved by Newton (see :doc:`solvers` for the linear core).
The **scheme** is how each interval is discretised — it sets the *accuracy*
and *stability* of the transition for a given grid.

The default is Crank–Nicolson (the implicit midpoint rule): second-order and
A-stable, a robust general-purpose choice. Three higher-order **collocation
families** are also available, selectable with their order; on a smooth
problem they reach a target accuracy on a far coarser grid.

This is independent of the *linear* backend (:doc:`solvers`) and the
*nonlinear steady-state* algorithm (:doc:`steady_solvers`): a run mixes them
freely. Every scheme here produces the same one-step (block-triangular)
coupling, so the linear backends and their cross-segment warm-start are
unaffected by the choice.

Choosing a scheme
-----------------

Three entry points, later overriding earlier (**CLI > directive > default**):

The ``simulate`` directive
   Pin the scheme (and order) with the model (see :doc:`language/commands`):

   .. code-block:: text

      simulate(T = 120, N = 300, scheme = radau, order = 5);

Python API
   Pass ``scheme=`` / ``order=`` to :meth:`continuo.Model.simul`:

   .. code-block:: python

      model.simul(scheme="gauss", order=4)

Command line
   Override at the call site:

   .. code-block:: console

      $ continuo model.mod --scheme radau --order 5

``order`` selects the collocation order within a family; omit it for the
family default. ``crank_nicolson`` is fixed second-order and takes no
``order``.

The families
------------

All four are *collocation* methods — they differ only in where the ``s``
stage nodes sit inside each interval; the order then follows from the node
count. The bound on accuracy is the **global order** ``p``: halving the step
cuts the error by about ``2^p``.

.. list-table::
   :header-rows: 1
   :widths: 18 14 14 26 28

   * - ``scheme``
     - order
     - ``order`` ∈
     - stability
     - use it for
   * - ``crank_nicolson``
     - 2
     - — (fixed)
     - A-stable, symmetric
     - the robust default
   * - ``gauss``
     - 2s
     - 2, 4, 6
     - A-stable, symmetric
     - smooth / conservative (orbits)
   * - ``radau``
     - 2s−1
     - 1, 3, 5
     - L-stable, stiffly accurate
     - stiff / sharp transitions
   * - ``lobatto_iiia``
     - 2s−2
     - 2, 4, 6
     - A-stable, endpoint nodes
     - BVP-native collocation

``gauss`` at order 2 is exactly Crank–Nicolson (the one-stage Gauss method is
the implicit midpoint), so the families extend the default rather than
replace it. ``radau`` is **L-stable** and stiffly accurate — the right choice
when the dynamics are stiff or the path has a sharp transition that A-stable
schemes resolve only on a fine grid.

How it works
------------

Each interval carries ``s`` internal **stage unknowns** (the stage
derivatives, plus the algebraic stage values for index-1 variables) appended
to the stacked vector after the node block. The model residual is composed
with the stage relations and differentiated by CasADi automatic
differentiation, so the exact Jacobian is preserved and the per-interval
coupling stays one-step. Stage unknowns are seeded from the node guess and
dropped from the returned path. Crank–Nicolson keeps its dedicated one-stage
form.

Accuracy
--------

On a smooth problem the error of a scheme of order ``p`` falls like ``h^p``.
The :doc:`Goodwin example <examples>` makes this concrete on a closed orbit:
against a fine reference, the max error over the trajectory is

.. list-table::
   :header-rows: 1
   :widths: 16 28 28 28

   * - ``N``
     - ``crank_nicolson`` (2)
     - ``gauss`` (4)
     - ``radau`` (5)
   * - 150
     - 2.7e-02
     - 2.3e-05
     - 5.3e-07
   * - 300
     - 6.9e-03
     - 1.4e-06
     - 1.6e-08
   * - 600
     - 1.7e-03
     - 9.0e-08
     - 5.2e-10
   * - 1200
     - 4.3e-04
     - 5.6e-09
     - 1.6e-11

— the higher-order schemes reach at ``N = 150`` an accuracy Crank–Nicolson
does not match at ``N = 1200``. Higher order pays off when the solution is
smooth; near a kink (an occasionally-binding constraint) or a discontinuous
shock the gain is limited by the non-smoothness, and refining ``N`` (or
Crank–Nicolson) can be the steadier choice.

.. note::

   The schemes above run on a uniform grid by default, but the grid need not
   be uniform: non-uniform and adaptively refined meshes — placing nodes where
   the solution varies fastest — build on this same collocation machinery. See
   :doc:`grids`.

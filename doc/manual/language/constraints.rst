Domain constraints
==================

Many endogenous variables live in a known range: a capital stock is
positive, a rate lies in ``(0, 1)``. The numerical steady-state solver does
not know this, and a trial iterate that leaves the domain produces a
``NaN`` (from ``K^alpha`` or ``log(K)`` at a negative ``K``) that derails
convergence. A **domain constraint** declares the range, and continuo then
solves so that the variable never leaves it.

Declaring a constraint
-----------------------

The constraint is part of the ``var`` qualifier, alongside the optional
``state`` / ``jump`` type (see :doc:`declarations`):

.. code-block:: text

   var(state, positive)             K;     // K > 0          ≡ boundaries=(0, inf)
   var(jump,  negative)             X;     // X < 0          ≡ boundaries=(-inf, 0)
   var(boundaries=(0, 1))           u;     // 0 < u < 1
   var(state, boundaries=(0, kmax)) L;     // 0 < L < kmax   (kmax a parameter)
   var(boundaries=(kmin, inf))      M;     // M > kmin

The qualifier is a comma-separated list carrying at most one **type**
(``state`` / ``jump``, omitted ⇒ algebraic) and at most one **constraint**:

``positive`` / ``negative``
   Shorthand for ``boundaries=(0, inf)`` and ``boundaries=(-inf, 0)``.

``boundaries=(lo, hi)``
   An explicit interval. Either side may be ``inf`` / ``-inf`` for an open
   (unbounded) direction; the other is a numeric bound.

The order of the type and the constraint is free (``var(positive, state) K;``
is the same declaration). A plain ``var(state) K;`` or ``var K;`` is
unconstrained, exactly as before.

Bounds as expressions
~~~~~~~~~~~~~~~~~~~~~~

A bound may be a literal or an expression over **parameters and exogenous
variables** — never an endogenous variable. The referenced names need only
be *declared somewhere* (declaration order does not matter) and carry a
value at solve time; the bound is evaluated then, under the current
parameter and exogenous configuration. A bound naming an endogenous
variable, or an undeclared name, is rejected when the model is read — on
every path, including when an analytical ``steady_state_model`` is present
(so a typo in a bound never passes silently). Two numeric-literal bounds
are checked for ``lower < upper``.

Strict, open domains only
-------------------------

The constraint is interpreted as the **open** interval ``(a, b)``: the
solver stays strictly inside it and never reaches a bound. This is by
construction — see the change of variable below — and it is the right model
when the solution is interior.

A solution that **saturates** a bound (sits exactly on it) is a different
problem — a mixed complementarity problem (MCP) — and needs different tools;
it is **out of scope** here. Domain constraints are also distinct from the
``min`` / ``max`` folds that may appear *in the model equations* (e.g. a
zero lower bound ``i = max(0, …)``), which are part of the equation itself
and can bind; see :doc:`expressions`.

How it works: the change of variable
-------------------------------------

continuo does not constrain the root-find. Instead it **reparametrises**:
it solves in an unconstrained variable ``y`` and maps it through a smooth,
invertible ``x = T(y)`` whose image is exactly the open domain. The
root-finder roams all of ``y``-space while ``x`` stays strictly inside
``(a, b)`` for every finite ``y`` — so the residual is never evaluated at an
out-of-domain ``x``, and the ``NaN`` failure mode disappears.

The map depends on which sides are bounded, with lower bound ``a`` and
upper bound ``b``:

.. list-table::
   :header-rows: 1
   :widths: 18 32 32 18

   * - Case
     - ``x = T(y)``
     - ``y = T⁻¹(x)``
     - ``T(0)``
   * - lower ``a``
     - ``a + exp(y)``
     - ``log(x - a)``
     - ``a + 1``
   * - upper ``b``
     - ``b - exp(y)``
     - ``log(b - x)``
     - ``b - 1``
   * - both ``a, b``
     - ``a + (b-a)/(1+e^{-y})``
     - ``log((x-a)/(b-x))``
     - midpoint

The transform is composed symbolically with the model residual, and CasADi
automatic differentiation supplies ``∂F/∂y`` through the chain rule — there
is no manual ``dx/dy`` factor, and the exact Jacobian the solvers rely on is
preserved. The choice of nonlinear backend (:doc:`../steady_solvers`) is
unaffected: ``auto`` and every preset work transparently in ``y``-space.

The starting iterate
~~~~~~~~~~~~~~~~~~~~~~

A constrained variable with no guess starts at ``y = 0``, i.e. the strictly
interior point ``T(0)`` (the midpoint for a two-sided interval). An explicit
``initial_guess`` (or a caller-supplied ``guess=``) is mapped back through
``T⁻¹``, which **requires it to be strictly interior** to the declared
domain: a guess on or outside a bound raises a ``SolveError``.

Disabling it: ``nodomain``
--------------------------

The ``nodomain`` flag on the ``steady`` directive turns the change of
variable off, solving in raw ``x`` even when constraints are declared — for
debugging, comparing the raw and reparametrised solves, or working around a
saturating solution:

.. code-block:: text

   steady(nodomain);              // solve in raw x, ignore the bounds
   steady(t = 5, nodomain);       // combines with the other options

The same control is available from the API as
``Model.steady_state(nodomain=True)``; ``nodomain=None`` (the default)
defers to the directive, an explicit bool overrides it — the same precedence
as ``solver``.

The analytical path
-------------------

When the model carries a ``steady_state_model`` block, the steady state is a
closed form and the numerical solver does not run; the constraints are
validated at build time but otherwise **inert** (no change of variable). This
is not an error — the bounds simply have nothing to act on.

A note on saturation
--------------------

For a solution very close to a bound, ``y`` grows large and the map
degenerates (``dx/dy → 0`` for the logistic, ``exp`` overflows for the
one-sided maps). The ``homotopy`` fallback of the ``auto`` chain and the
non-finite-residual guard still apply, but there is no clamping. If a model
genuinely saturates a bound, drop the constraint and use ``nodomain``, or
treat it as the complementarity problem it is.

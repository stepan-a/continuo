Python API
==========

The top-level :mod:`continuo` package exposes a small, focused API: a
parser, a model object that wraps the parsed file with its solvers, and
a solution object that wraps the solved path. The remaining modules
(parser, IR, codegen, solve) are public to the extent that their
exceptions are catchable by the user, but their internals are
implementation details.

.. currentmodule:: continuo

Entry points
------------

.. autofunction:: parse
.. autofunction:: parse_string

The ``Model`` object
--------------------

.. autoclass:: continuo.api.Model
   :members:

The ``Solution`` object
-----------------------

.. autoclass:: continuo.io.solution.Solution
   :members:

A ``Solution`` aggregates one or more :class:`~continuo.io.solution.Segment`
records (one per active belief — see :doc:`language/shocks`):

.. autoclass:: continuo.io.solution.Segment
   :members:

Diagnostics
-----------

``Solution.diagnostics`` is a free-form ``dict`` populated by the solver
with run-level summary information. The keys currently set are:

``scheme`` (``str``)
   The discretisation scheme that was used (e.g. ``"crank_nicolson"``).
   Matches the ``scheme`` argument of the ``simulate`` command.

``segments`` (``int``)
   Number of perfect-foresight segments the orchestrator solved. Equals
   ``1`` when no surprise revelations split the horizon, and ``1 + k``
   when ``k`` surprise reveal times fall inside ``[0, T]``.

``newton_iterations`` (``int``)
   Total Newton iterations summed across all segments. A sudden jump
   from one run to the next — same model, similar parameters — usually
   means the new instance is closer to a singularity or the initial
   guess is poorer; inspect the per-segment counts via
   ``[seg.iterations for seg in sol.segments]``.

``solver`` (``str``)
   The linear backend that was used (e.g. ``"klu"``, ``"superlu"``).
   See :doc:`solvers`.

``factorizations`` / ``refactorizations`` (``int``)
   How many full factorisations versus cheap refactorisations the
   backend performed over the run. With the cross-segment warm-start, a
   two-segment surprise typically shows one factorisation and one
   refactorisation.

``refactor_fallbacks`` (``int``)
   How many times a reused factorisation failed (a stale-pivot
   re-pivot) and was redone from scratch. Normally ``0``.

``min_rcond`` (``float`` or ``None``)
   The worst reciprocal-condition estimate seen over the run, or
   ``None`` when the backend exposes none (SuperLU, PARDISO).

``fill`` (``int`` or ``None``)
   The factorisation fill ``nnz(L) + nnz(U)``, where the backend
   exposes it (SuperLU, UMFPACK); ``None`` otherwise.

The same summary is also emitted at ``logging.INFO`` level on the
``continuo.solve.orchestrator`` logger, so a caller that configures
``logging.basicConfig(level=logging.INFO)`` will see one line per run
without having to read the dict.

The set of keys may grow in future releases; treat unknown keys as
informational and the documented ones as the stable contract.

Exceptions
----------

Each pipeline stage raises a dedicated exception so user code can
distinguish where a problem originated. All four inherit from
``Exception`` (not from one another); a CLI-style "any pipeline error"
catch is ``except (MacroError, LarkError, IRError, CodegenError,
SolveError)``.

.. autoexception:: continuo.macro.MacroError
.. autoexception:: continuo.ir.IRError
.. autoexception:: continuo.codegen.CodegenError
.. autoexception:: continuo.solve.SolveError

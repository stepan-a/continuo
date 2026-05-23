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

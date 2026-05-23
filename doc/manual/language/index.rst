The ``.mod`` language
=====================

A ``.mod`` file is a sequence of blocks describing the model, its
steady state, its initial conditions and the exogenous paths, plus the
commands that drive the solver. The order of blocks is largely free —
the parser is order-insensitive — but the conventional order, used in
all shipped examples, is

1. variable and parameter declarations,
2. parameter values,
3. the ``model;`` block,
4. ``initval;`` (and optionally ``initial_guess;``),
5. ``steady_state_model;``,
6. ``shocks;``,
7. one or more commands (``simulate;``, ``steady;``).

Comments are written with ``//`` (line) or ``/* … */`` (block), exactly
as in Dynare.

This part of the manual documents each construct in turn:

.. toctree::
   :maxdepth: 1

   declarations
   model
   steady_state
   boundary
   shocks
   commands
   expressions
   macros

Expressions
===========

This page collects the expression sub-language: the operators,
functions, and literals that may appear on the right of an equation, in
a parameter assignment, in an ``initval``, in a steady-state assignment
or in a shock path. The same grammar applies everywhere; the only
context-dependent restrictions are noted below.

Literals
--------

``42``, ``3.14``, ``1.5e-3``
   Decimal literals (integer, fractional, optional exponent).

``'hello'`` or ``"hello"``
   String literals. Only meaningful as equation tags and similar
   metadata; using one in a numeric position raises a ``CodegenError``.

``{key1: expr, key2: expr}`` or ``{}``
   Dict literals. Used only as the value of the ``e=`` keyword in
   ``initval(steady, e={…})`` and ``steady_state(v, e={…})``; using one
   in a numeric position raises a ``CodegenError``.

Identifiers
-----------

Any declared name resolves to its value at the point of evaluation:

- a ``parameter`` resolves to its assigned value;
- a ``var`` (endogenous) resolves to its current state on the grid;
- a ``varexo`` resolves to the value at the current time of the active
  shock path;
- the built-in ``t`` resolves to the current time.

Arithmetic operators
--------------------

==========  ==========================
Operator    Meaning
==========  ==========================
``+``       Addition
``-``       Subtraction / unary minus
``*``       Multiplication
``/``       Division
``^``       Power (right-associative)
==========  ==========================

Precedence (low → high): ``+ -``, ``* /``, unary ``-``, ``^``. Use
parentheses for any clarification.

Comparison and logical operators
--------------------------------

Comparisons return 0 or 1 (as in Dynare):

- ``<``, ``<=`` — less-than, less-or-equal;
- ``>``, ``>=`` — greater-than, greater-or-equal;
- ``==`` — equal;
- ``!=`` — not equal.

Logical operators on these 0/1 values:

- ``&&`` — logical AND;
- ``||`` — logical OR;
- ``!`` — logical NOT.

Comparisons are **non-chainable** (``a < b < c`` is a syntax error;
write ``a < b && b < c``).

Mathematical functions
----------------------

The functions below are available in every block that accepts
expressions:

- exponentials and logs: ``exp``, ``ln`` (alias ``log``), ``log10``,
  ``sqrt``;
- trigonometric and hyperbolic: ``sin``, ``cos``, ``tan``,
  ``asin``, ``acos``, ``atan``, ``sinh``, ``cosh``, ``tanh``;
- error function: ``erf``;
- pointwise: ``abs``, ``sign``;
- variadic: ``min(a, b, …)``, ``max(a, b, …)`` (at least two arguments).

The conditional ``if(condition, then, else)`` (with the 1-argument sugar
``if(cond, x) ≡ if(cond, x, 0)``) is allowed everywhere.

.. note::

   ``min`` and ``max`` are useful for occasionally-binding constraints
   such as the ZLB (``i = max(0, …)``). Newton may have trouble at the
   kink for some calibrations; if convergence fails, raise ``N`` or
   use a smooth approximation like ``0.5*(z + sqrt(z*z + eps))`` in
   place of ``max(0, z)``.

   These folds live **in the equations** and may bind — they are distinct
   from the **domain constraints** declared on a ``var`` qualifier
   (:doc:`constraints`), which keep a variable *strictly* inside an open
   range and are never active at the solution.

Context-specific extras
-----------------------

The **shock-shape helpers** (``step``, ``pulse``, ``ramp``, ``bump``,
``expdecay``, ``smoothstep``) are available **only inside ``shocks``
paths** and are rejected in ``model`` equations. See :doc:`shocks`.

The **time derivative** ``diff(x)`` is allowed only inside the
``model`` block (and as a left-hand side in ``initval``).

The **steady-state callable** ``steady_state(var)`` and
``steady_state(var, e={…})`` is allowed only inside the ``initval``
block; see :doc:`boundary`.

Comments
--------

``//`` introduces a line comment, ``/* … */`` a block comment. Comments
are ignored by the parser.

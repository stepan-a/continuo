The macroprocessor
==================

Before the model parser sees a ``.mod`` file, a **macroprocessor**
expands a small set of Dynare-compatible directives. It is a
pure text-transformation pass: a directive line is one whose first
non-blank characters are ``@#``; everything else is verbatim text.

The macroprocessor preserves source positions so that error messages
from the model parser point at the right place in the original file
(through any number of expansion frames).

Including other files
---------------------

.. code-block:: text

   @#include "common.mod"

Splices the contents of another file at this point. Paths are resolved
relative to the *including* file (and then against an optional search
list set with ``@#includepath``). Circular includes are rejected.

Includes are the primary tool for factoring shared declarations and
the ``model`` block out of multiple scenarios; the shipped examples
under ``examples/`` use this systematically.

.. code-block:: text

   @#includepath "../shared"   // add to the include search list
   @#include "params.mod"

Definitions
-----------

``@#define`` introduces a macro name (a value bound at the macro level —
this is *not* the same thing as a model parameter):

.. code-block:: text

   @#define ALPHA = 0.33
   @#define COUNTRIES = ["fr", "de", "it"]

With a parameter list, ``@#define`` instead binds a **macro function** — its
body is evaluated with the arguments substituted for the parameters:

.. code-block:: text

   @#define spread(a, b) = a - b
   @#define tagged(xs)   = [ "K_" + string(x) for x in xs ]

The right-hand side is the macro expression language (see below). Inside
model text, ``@{...}`` interpolates the value of an expression at the place
of the braces:

.. code-block:: text

   parameters alpha;
   alpha = @{ALPHA};

The macro expression language
-----------------------------

Macro expressions — in ``@#define``, ``@{...}``, conditions, and ``@#for``
iterables — are evaluated by a small language, distinct from the model's own
expressions (:doc:`expressions`):

- **Values**: integers and reals, strings, booleans (``true`` / ``false``),
  lists ``[…]`` and tuples ``(…)``.
- **Operators**: arithmetic ``+ - * / ^`` (``^`` is power), comparisons
  ``== != < <= > >=``, membership ``in``, and boolean ``&&`` / ``||`` / ``!``.
  ``+`` also concatenates two strings or two lists, and ``-`` between two
  lists is set-difference (drop the right operand's elements from the left).
- **Ranges**: ``a:b`` is the inclusive integer range (Dynare-style), so
  ``1:3`` is ``[1, 2, 3]``.
- **Indexing**: ``xs[i]`` is **1-based**, as in Dynare.
- **List comprehensions**: ``[ f(x) for x in xs if cond ]``, with one or more
  ``for`` / ``if`` clauses.
- **Builtins**: maths (``exp``, ``ln``, ``log``, ``log10``, ``sqrt``, the
  trigonometric and inverse-trigonometric functions, ``erf`` / ``erfc``),
  numeric helpers (``abs``, ``sign``, ``floor``, ``ceil``, ``trunc``,
  ``round``, ``mod``, ``power``, ``min`` / ``max``, ``sum``, ``length``,
  ``normpdf`` / ``normcdf``), type predicates (``isreal``, ``isinteger``,
  ``isstring``, ``isboolean``, ``isarray``, ``istuple``, ``isempty``), and the
  casts / constructors ``string``, ``real``, ``bool``, ``range(lo, hi[,
  step])``.

These fold *macro* values at expansion time; they are unrelated to the
model-level ``min`` / ``max`` / ``log`` that act on model variables at solve
time.

Conditionals
------------

.. code-block:: text

   @#if SOME_FLAG > 0
     // text included when the condition is true
   @#elseif OTHER_FLAG
     // ...
   @#else
     // fallback
   @#endif

The shorthand ``@#ifdef NAME`` / ``@#ifndef NAME`` tests whether a macro
is defined, regardless of its value:

.. code-block:: text

   @#ifdef ZLB
     i = max(0, rho + phipi*pi + phix*x);
   @#else
     i = rho + phipi*pi + phix*x;
   @#endif

Loops
-----

``@#for`` iterates a name (or a parenthesised tuple of names) over a list
(to loop over a filtered subset, filter the list with a comprehension —
``@#for x in [y for y in LIST if cond]``):

.. code-block:: text

   @#for c in COUNTRIES
   var(state) K_@{c};
   var Y_@{c};
   @#endfor

   @#for (i, j) in [(1, 2), (3, 4)]
     Y_@{i}_@{j} = ...;
   @#endfor

The body is expanded once per iteration with the loop variable(s) bound
to the current value.

Echo and diagnostics
--------------------

``@#echo`` and ``@#error`` evaluate a message expression at expansion time:
``@#echo`` prints it (a build-time note), ``@#error`` aborts the expansion
with it.

.. code-block:: text

   @#echo "building " + string(length(COUNTRIES)) + " countries"
   @#if length(COUNTRIES) == 0
   @#error "COUNTRIES is empty"
   @#endif

``@#echomacrovars`` dumps the current macro environment (every defined name
and its value) — a debugging aid.

Error reporting
---------------

A macro-time error (unknown identifier, type mismatch, missing
``@#endif``, …) is reported with the source position in the *original*
file. Errors that surface later — at the parser or the IR — also carry
the original source position through the line map: a model error that
arose inside an expanded ``@#for`` body shows the loop's iteration in
the message.

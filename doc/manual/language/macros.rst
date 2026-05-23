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

The right-hand side is a small expression language (numbers, strings,
lists, tuples, arithmetic, comparisons, indexing). Inside model text,
``@{...}`` interpolates the value of an expression at the place of the
braces:

.. code-block:: text

   parameters alpha;
   alpha = @{ALPHA};

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

``@#for`` iterates a name (or a parenthesised tuple of names) over a
list, with an optional ``if`` filter:

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

Error reporting
---------------

A macro-time error (unknown identifier, type mismatch, missing
``@#endif``, …) is reported with the source position in the *original*
file. Errors that surface later — at the parser or the IR — also carry
the original source position through the line map: a model error that
arose inside an expanded ``@#for`` body shows the loop's iteration in
the message.

# continuo reference manual

This is the Sphinx source for the continuo reference manual. The
rendered HTML lives in `_build/html/` (gitignored).

## Building

Install the doc dependencies once:

```console
$ pip install -e ".[docs]"      # adds sphinx, furo, sphinx-copybutton
```

then build:

```console
$ cd doc/manual
$ make html
$ xdg-open _build/html/index.html
```

The Python API page uses `sphinx.ext.autodoc`, which imports the
package — installing continuo (editable or otherwise) is enough; the
`conf.py` also adds `src/` to `sys.path` as a fallback, so the build
works straight from a clone without installing.

## Layout

```
conf.py                 Sphinx configuration (furo theme, autodoc, napoleon)
index.rst               Top-level TOC
installation.rst        Install instructions
quickstart.rst          Smallest end-to-end example
language/               The .mod surface-language reference
   index.rst
   declarations.rst     var / varexo / parameters
   model.rst            The model block (equations, diff, tags)
   steady_state.rst     The steady_state_model block
   boundary.rst         initval, initial_guess, the e={…} override
   shocks.rst           Shock paths, shape helpers, surprises
   commands.rst         simulate, steady
   expressions.rst      Operators, math functions, comparisons
   macros.rst           @#include / @#define / @#if / @#for / ...
api.rst                 Python API (autodoc)
cli.rst                 Command-line reference
examples.rst            Index of the shipped example models
```

## Conventions

- `.mod` code blocks are highlighted as plain `text` (`highlight_language
  = "text"` in `conf.py`); Pygments has no Dynare lexer, and using `c`
  or `matlab` introduced spurious "error" tokens.
- The Python API page is generated from docstrings; keep them accurate
  rather than duplicating signatures in the `.rst`.

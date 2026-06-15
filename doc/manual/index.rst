Continuo |release|
==================

**continuo** solves continuous-time, perfect-foresight deterministic
dynamic models in the spirit of Dynare. A ``.mod`` file declares the
endogenous and exogenous variables, the model equations (as differential
equations in continuous time, written with ``diff(x)``), the steady state
and the exogenous shock paths; the toolbox parses it, discretises the
two-point boundary-value problem with a Crank–Nicolson collocation, and
solves the stacked nonlinear system with Newton's method. Anticipated
changes, surprises (multi-segment beliefs) and occasionally-binding
constraints are all supported through the same machinery.

The toolbox has three faces:

- the ``.mod`` surface language (the canonical input format),
- a Python API (:mod:`continuo`) for use in scripts and notebooks,
- a command-line wrapper ``continuo`` that reads a ``.mod`` file and
  writes the solved path to CSV.

This manual is the reference for all three. The :doc:`quickstart` shows
the smallest end-to-end use; the :doc:`language/index` documents every
block and built-in of the surface language; :doc:`api` is the Python
reference (generated from docstrings); :doc:`solvers` documents the
pluggable linear backends and how to choose one; :doc:`examples` is the
index of the worked-out example models that ship with the source tree.

.. toctree::
   :maxdepth: 2
   :caption: Getting started

   installation
   quickstart

.. toctree::
   :maxdepth: 2
   :caption: Reference

   language/index
   api
   solvers
   cli
   examples

Indices
=======

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

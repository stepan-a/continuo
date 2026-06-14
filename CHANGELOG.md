# Changelog

All notable changes to **continuo** are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versioning
follows [Semantic Versioning](https://semver.org).

## [0.0.1] — 2026-05-23

First tagged release. The package was unversioned before this point;
this entry summarises what is in the source tree at the time of tagging
rather than what changed since a previous release.

### Surface language and parser

- Lark-based parser for the `.mod` surface language: variable
  declarations (`var(state)`, `var(jump)`, `var`, `varexo`, `parameters`),
  the `model;` block (explicit `LHS = RHS;` and bare `expr;` forms,
  with optional `[tag='value']` annotations), `steady_state_model;`,
  `initval;` and `initial_guess;` with the `(steady [, e={…}])` sugar,
  the `shocks;` block with `path = …` and `path at t=T = …` for
  multi-revelation surprises, and the commands `simulate(…);` and
  `steady;`/`steady(…);`.
- Macroprocessor running before the parser: `@#include`, `@#includepath`,
  `@#define`, `@#if`/`@#elseif`/`@#else`/`@#endif`,
  `@#ifdef`/`@#ifndef`, `@#for`/`@#endfor`, and `@{expr}` inline
  expansions. Source positions are preserved through a line map, so
  errors at any later stage point back to the original file.

### Intermediate representation, codegen and solver

- IR build pipeline (reduce, classify, boundary, steady-state, shocks,
  commands) with thorough validation; equations are reduced to first
  order; states/jumps/algebraic are classified from declarations and
  usage, and inconsistencies are reported with source positions.
- CasADi-based expression lowering covering arithmetic, comparison and
  logical operators, the standard math library
  (`exp`, `ln`/`log`, `log10`, `sqrt`, trig, hyperbolic, `erf`, `abs`,
  `sign`, variadic `min`/`max`) and the conditional `if(cond, a[, b])`.
- Stacked collocation on the Crank–Nicolson (implicit-midpoint) scheme
  with sparse Newton, backtracking line search and analytical or
  numerical steady-state seeding.
- Multi-segment orchestrator: anticipated, permanent, and surprise
  (MIT-style) shocks are stitched by state continuity, with each
  segment solved under the belief active at its start.

### Shock-shape helpers

- `step`, `pulse`, `ramp`, `bump`, `expdecay`, `smoothstep` — lowered
  in `codegen.translate` and gated to shock-path expressions (rejected
  in `model` equations).

### Boundary anchoring

- `initval(steady, e={…})` resolves the initial steady state at the
  active exogenous overridden by the given values; the same override
  works on the per-state callable `steady_state(v, e={…})`. Override
  keys are validated against the declared `varexo`.

### Python API and CLI

- `continuo.parse(path)` and `continuo.parse_string(source)` return a
  `Model` with `.simul()`, `.steady_state()` and inspection properties.
  `Solution` and `Segment` wrap the solved path with NumPy arrays and
  optional pandas / xarray conversions.
- `continuo` CLI: parses a `.mod` file, runs the simulation, and
  writes the solved path to CSV with optional `-T`/`-N`/`-o` overrides.

### Examples

Seven worked example folders under `examples/`, each with a shared
`common.mod` pulled in by per-scenario files via `@#include`, a
`run_<name>.py` overlay script and a `README.md` presenting the model
and the simulation results:

- `rbc/` — Ramsey/RBC with anticipated, surprise and permanent shocks.
- `solow/` — Solow–Swan (pure IVP, one state, no jump).
- `cagan/` — money and prices (pure forward-looking, one jump).
- `dornbusch/` — exchange-rate overshooting (sticky-price saddle).
- `tobinq/` — Tobin's *q* investment with adjustment costs.
- `nk/` — New Keynesian liquidity trap with the ZLB (`max(0, …)`).
- `goodwin/` — Lotka–Volterra growth cycle (closed orbits, no
  terminal condition).

### Documentation

- Sphinx reference manual under `doc/manual/` covering the `.mod`
  surface language (declarations, model, steady-state, boundary,
  shocks, commands, expressions, macros), the Python API (autodoc),
  the CLI, and an index of the shipped examples.

### Tooling

- 643 tests; `ruff` configured for `src` and `tests`. GitLab CI runs
  `lint`, `tests`, `docs` (Sphinx build with warnings-as-errors) and
  `deploy_docs` (rsync to https://continuo.adjemian.eu) on every push
  to `master`.
- `scripts/bump-version.py` — single-command release helper that
  updates the version across `pyproject.toml`, `README.md`,
  `tests/test_smoke.py`, `doc/manual/conf.py` and inserts a fresh
  `CHANGELOG.md` entry template. Supports `--check` (dry-run) and
  validates monotonicity.

### Known limitations

- The `steady_state(var, …)` callable inside `model` equations
  (terminal-SS-per-segment, `t=` override) described in the spec is
  not yet implemented; only the `initval`-side override is wired up.
- Grid auto-alignment to the shock-shape helpers' discontinuity
  locations is deferred; paths are sampled pointwise on the uniform
  grid, so a discontinuity that falls between nodes is smeared by up
  to one `dt`.
- Only the Crank–Nicolson discretisation scheme is implemented;
  Radau, SDIRK and Lobatto IIIA are deferred.

[0.0.1]: https://github.com/stepan-a/continuo/releases/tag/v0.0.1

# Changelog

All notable changes to **continuo** are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versioning
follows [Semantic Versioning](https://semver.org).

## [0.0.2] — 2026-06-16

### Solver

- Introduce a pluggable linear-solver interface (`solve/linsolve.py`):
  the `LinearSolver` protocol exposes the `analyze` / `factor` /
  `refactor` / `solve` phases so the constant sparsity pattern of the
  stacked Jacobian is analysed once and the numeric factorisation is
  refreshed cheaply at each Newton step. The Newton core now drives the
  linear solve through this interface, with `SuperluSolver` (SciPy, the
  always-available backend) as the default — no change in results.
- Add a `solver=` option to `Model.simul`, `continuo.solve_pf` and
  `simulate`: a preset name (`"superlu"`, `"auto"`), a `LinearSolver`
  instance for fine control, or `None` (the `"auto"` default). The
  selected backend is recorded in the run diagnostics, and unknown or
  unavailable presets raise a clear `SolveError`. A registry
  (`SOLVERS`, `available_solvers`, `select_solver`) backs the choice;
  optional backends register there in later releases.
- Add the `klu` / `klu-nobtf` backends (`KluSolver`): a `ctypes` binding
  to SuiteSparse KLU (`solve/_klu.py`) that reuses its symbolic analysis
  across numeric refactorisations — a cheap `refactor` per Newton step
  instead of a full factorisation, the main per-step win. `btf` is a
  parameter of `KluSolver` (block-triangular pre-ordering, off for plain
  sparse LU), and `ordering` selects AMD or COLAMD. The library is detected at runtime: `klu` is
  offered only when `libklu.so` is present (Debian `libsuitesparse-dev`),
  and a structurally singular Jacobian is reported at analysis time.
- Route `solver="auto"` (the default) by the scheme's coupling stencil:
  one-step schemes (Crank–Nicolson) now pick `klu` when it is available —
  whose amortised refactorisation is fastest here — and fall back to
  `superlu` otherwise (warning once). The multi-segment orchestrator
  analyses the constant sparsity pattern **once** and reuses it across
  segments, carrying the factorisation forward to warm-start each
  segment's first Newton step (a refactor reusing the pivot order, with a
  safe fall-back to a full factor).
- Add the optional `umfpack` and `pardiso` backends (`UmfpackSolver`,
  `PardisoSolver`) and the `umfpack` / `pardiso` / `solvers` extras.
  UMFPACK (`scikit-umfpack`) separates symbolic and numeric phases cleanly
  and reports `rcond`; PARDISO (`pypardiso`, MKL, multithreaded) factorises
  and solves for large / multi-core runs. Each is offered only when its
  package is importable (probed without importing it, so the MKL load is
  not paid unless PARDISO is actually used). Both remain non-default —
  `auto` prefers KLU for one-step schemes.
- Enrich the run diagnostics with per-solver statistics (a `SolveStats`
  accumulator): counts of full `factorizations` versus cheap
  `refactorizations`, the number of `refactor_fallbacks` (safety
  re-pivots), the worst `min_rcond` over the run, and the factorisation
  `fill` (`nnz(L) + nnz(U)`, where the backend exposes it — SuperLU and
  UMFPACK). The orchestrator's per-run log line now reports the
  factor/refactor split.
- Accept a `solver=` option on the `simulate` directive, e.g.
  `simulate(T=50, N=250, solver=klu);` (or `solver="klu-nobtf"` for the
  dashed preset). Unknown names are rejected at validation. Precedence is
  explicit argument (API / CLI) > directive > `auto`.
- Add a `--solver` flag to the `continuo` CLI
  (`continuo model.mod --solver klu`), overriding the directive.

### Documentation

- Add a "Linear solvers" reference page to the manual (backends, presets,
  `auto` routing, fine control, guard-rails, diagnostics) and document the
  `solver=` directive, the `--solver` flag, the new diagnostics keys, and
  the optional-backend install (`libsuitesparse-dev`, the `umfpack` /
  `pardiso` / `solvers` extras).
- Add `examples/benchmark_solvers.py`, which benchmarks every available
  backend across the example models (each in an isolated subprocess) and
  regenerates the comparison tables in the README and manual (`--write`).
  Two modes: end-to-end `Model.simul()` wall-clock and peak memory, and an
  isolated micro-benchmark (`--micro`) timing only the linear-solve phases
  (`factor + solve`, `refactor + solve`) on each model's real stacked
  Jacobian — where KLU's amortised refactorisation shows a ~7× edge.

### Tooling

- GitHub CI now builds and publishes a GitHub Release on every version
  tag (`v*`), attaching the built sdist and wheel.

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

[0.0.2]: https://github.com/stepan-a/continuo/releases/tag/v0.0.2
[0.0.1]: https://github.com/stepan-a/continuo/releases/tag/v0.0.1

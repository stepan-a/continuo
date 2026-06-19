# Continuo

[![release](https://img.shields.io/github/v/release/stepan-a/continuo)](https://github.com/stepan-a/continuo/releases/latest)
[![tests](https://github.com/stepan-a/continuo/actions/workflows/tests.yml/badge.svg)](https://github.com/stepan-a/continuo/actions/workflows/tests.yml)
[![coverage](https://raw.githubusercontent.com/stepan-a/continuo/python-coverage-comment-action-data/badge.svg)](https://htmlpreview.github.io/?https://github.com/stepan-a/continuo/blob/python-coverage-comment-action-data/htmlcov/index.html)
[![GitLab CI](https://git.ithaca.fr/stepan/continuo/badges/master/pipeline.svg?key_text=GitLab%20CI&key_width=62)](https://git.ithaca.fr/stepan/continuo/-/pipelines)

Continuous-time DSGE toolbox in the spirit of Dynare. A Python toolbox
for solving continuous-time macroeconomic models, with perfect-foresight
deterministic transitions, multi-revelation surprises, and permanent
parameter changes.

**Status: pre-alpha (v0.0.3, 2026-06-16).** The pipeline runs end to end
— a `.mod` file solves to a path — and a reference manual ships with the
source, but interfaces may still change. See [`CHANGELOG.md`](CHANGELOG.md)
for what is in this release.

## Features

- Continuous-time perfect-foresight solver: stacked collocation
  (Crank–Nicolson) + Newton on a sparse two-point boundary value problem.
- Multi-segment information structures: anticipated, permanent, and
  MIT-style surprise shocks, stitched by state continuity.
- Macroprocessor compatible with Dynare's `@#define`, `@#if`, `@#for`,
  `@#include` (plus function macros, comprehensions, and a real-math
  library).
- Symbolic model representation, sparsity-aware Jacobians and C codegen
  via CasADi; sparse linear solve via SciPy.
- A CLI (`continuo model.mod`) and a programmatic Python API
  (`import continuo`).

Deferred: discretisation schemes beyond Crank–Nicolson (Radau,
Lobatto-IIIA), adaptive meshes, and HDF5/parquet output.

## Documentation

- [**Reference manual**](https://continuo.adjemian.eu/)
- [**Solving continuous-time perfect-foresight models**](https://continuo.adjemian.eu/pdf/perfect-foresight.pdf)

## Installation

Continuo is pure Python (≥ 3.13). Install the **latest release** without
cloning — the wheel is attached to every
[GitHub release](https://github.com/stepan-a/continuo/releases/latest):

```bash
pip install https://github.com/stepan-a/continuo/releases/download/v0.0.3/continuo-0.0.3-py3-none-any.whl
```

With the optional extras for the `Solution` conversion methods
(`to_dataframe`, `to_xarray`, HDF5 output):

```bash
pip install "continuo[pandas,xarray,hdf5] @ https://github.com/stepan-a/continuo/releases/download/v0.0.3/continuo-0.0.3-py3-none-any.whl"
```

To hack on the source, clone and install editable:

```bash
git clone https://github.com/stepan-a/continuo
cd continuo
pip install -e ".[dev]"
```

## Usage

A small model, `rbc.mod` — a one-sector growth model with an anticipated
rise in productivity `z` at `t = 5`, starting 20% below the steady state:

```
var(state) K;
var(jump)  C;
var        Y;
varexo     z;
parameters alpha, delta, rho;
alpha = 0.33;  delta = 0.1;  rho = 0.05;

model;
  diff(K) = Y - C - delta * K;              // capital accumulation
  diff(C) = C * (alpha * Y / K - delta - rho);   // Euler equation
  Y = z * K^alpha;                          // production
end;

steady_state_model;
  K = (alpha * z / (rho + delta))^(1 / (1 - alpha));
  Y = z * K^alpha;
  C = Y - delta * K;
end;

initval; K = 0.8 * steady_state(K); end;    // start below the steady state
shocks;  var z; path = if(t >= 5, 1.1, 1.0); end;
simulate(T=50, N=250);
```

From Python:

```python
import continuo

model = continuo.parse("rbc.mod")
sol = model.simul()                 # reads the simulate command

sol.t                               # time grid (numpy array)
sol["C"]                            # the consumption path
sol.K                               # attribute-style access

model.steady_state(exogenous={"z": 1.1})    # steady state under the new TFP
sol.to_dataframe()                  # pandas DataFrame (optional extra)
```

From the command line (writes `rbc.csv`):

```bash
continuo rbc.mod
continuo rbc.mod -o out.csv -T 100 -N 500   # override output / horizon / grid
```

## Solver benchmarks

The Newton solve runs on a pluggable linear backend (see the
[Linear solvers](https://continuo.adjemian.eu/solvers.html) manual page).
The table below compares the available backends across the example models;
regenerate it with `python examples/benchmark_solvers.py --write`.

<!-- BENCHMARK:START -->

**Wall-clock per solve (median, ms)**

| Model | n | superlu | klu | klu-nobtf | umfpack | pardiso |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| cagan | 201 | 18.2 | 18.4 | 19.7 | 18.3 | 261.0 |
| dornbusch | 903 | 23.3 | 23.8 | 23.4 | 23.6 | 261.1 |
| goodwin | 4802 | 133.8 | 122.6 | 122.3 | 133.0 | 375.2 |
| nk | 1503 | 79.5 | 82.5 | 79.8 | 79.2 | 318.0 |
| nk-nonlinear | 3005 | 113.1 | 109.6 | 113.1 | 113.4 | 360.6 |
| rbc | 1004 | 28.0 | 26.0 | 27.0 | 26.2 | 255.2 |
| solow | 602 | 25.7 | 24.2 | 25.5 | 25.4 | 268.0 |
| tobinq | 903 | 28.2 | 28.3 | 27.8 | 28.4 | 273.1 |

**Isolated linear solve — refactor + solve, warm (µs)**

| Model | n | superlu | klu | klu-nobtf | umfpack | pardiso |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| cagan | 201 | 44.7 | 11.3 | 11.0 | 18.5 | 459.4 |
| dornbusch | 903 | 160.4 | 25.6 | 31.6 | 255.5 | 1004 |
| goodwin | 4802 | 834.9 | 108.1 | 98.9 | 1299 | 2999 |
| nk | 1503 | 275.0 | 42.2 | 45.9 | 447.0 | 2583 |
| nk-nonlinear | 3005 | 476.2 | 62.4 | 129.9 | 868.8 | 2051 |
| rbc | 1004 | 294.5 | 29.7 | 47.2 | 284.8 | 1218 |
| solow | 602 | 117.1 | 20.4 | 18.3 | 136.3 | 530.9 |
| tobinq | 903 | 135.6 | 24.8 | 25.7 | 184.0 | 982.0 |

**Peak resident memory (MiB)**

| Model | n | superlu | klu | klu-nobtf | umfpack | pardiso |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| cagan | 201 | 102 | 100 | 100 | 101 | 139 |
| dornbusch | 903 | 103 | 101 | 101 | 102 | 142 |
| goodwin | 4802 | 116 | 113 | 112 | 114 | 169 |
| nk | 1503 | 105 | 102 | 103 | 104 | 146 |
| nk-nonlinear | 3005 | 112 | 108 | 109 | 110 | 158 |
| rbc | 1004 | 105 | 103 | 102 | 103 | 144 |
| solow | 602 | 103 | 101 | 101 | 101 | 141 |
| tobinq | 903 | 105 | 102 | 103 | 103 | 142 |

**Reading these:** the wall-clock above is *end-to-end* `Model.simul()`, dominated by the (solver-independent) CasADi build and residual/Jacobian evaluation — so on these small models the linear backend barely moves it. KLU's edge is in the linear solve itself: the isolated `refactor + solve` table (the warm per-Newton-step cost) shows it ~4–10× faster than SuperLU, a gap that grows with problem size and Newton iterations. PARDISO is far slower here only because MKL oversubscribes threads on these tiny systems — reserve it for large models. See the [Linear solvers](https://continuo.adjemian.eu/solvers.html) manual page for the full isolated tables.

_Median of 5 runs of end-to-end `Model.simul()` (includes the CasADi build). Wall-clock in milliseconds; peak resident memory in MiB (whole process — the Python/CasADi/SciPy baseline dominates, and PARDISO loads MKL). Measured 2026-06-19 on AMD Ryzen AI 9 HX 370 w/ Radeon 890M, 24 cores, Python 3.13.14._

<!-- BENCHMARK:END -->

## Running the testsuite

The tests live in `tests/` and are driven by `pytest`. The repository is
configured for [`nox`](https://nox.thea.codes/), which builds an isolated
virtual environment for each task — mirroring how CI runs. Install nox once
(globally, not into the project):

```bash
pipx install nox          # recommended; provides a `nox` command
# or: pip install --user nox
# or, on Debian/Ubuntu: apt install python3-nox  (then invoke as `python3 -m nox`)
```

The Debian `python3-nox` package does not install a `nox` launcher on your
`PATH`; if you used it, replace `nox` with `python3 -m nox` below. Then run
the sessions:

```bash
nox                     # default sessions: lint + tests on the current Python
nox -s tests            # tests across Python 3.13 and 3.14
nox -s lint             # ruff check + format check (as in CI)
nox -s fix              # apply ruff autofixes and reformat in place
nox -s coverage         # tests with a coverage report
nox -l                  # list all sessions
```

Arguments after `--` are forwarded to `pytest`, so you can narrow a run:

```bash
nox -s tests -- tests/parser     # only the parser tests
nox -s tests -- -k shocks        # only tests whose name matches "shocks"
```

The matrix in `nox -s tests` needs the corresponding interpreters installed;
run a single one with e.g. `nox -s tests-3.13`.

### Without nox

You can also run the tools directly. Install the package with its
development dependencies in editable mode, ideally inside a virtual
environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Then, from the repository root:

```bash
pytest                       # full suite (tests/ is discovered automatically)
pytest -q --tb=short         # quiet output, short tracebacks (as in CI)
pytest tests/parser          # only the parser tests
pytest -k shocks             # only tests whose name matches "shocks"
pytest --cov=continuo       # with a coverage report

ruff check src tests         # lint (as in CI)
ruff format --check src tests # formatting check (as in CI)
```

## License

Released into the public domain under the [Unlicense](https://unlicense.org/).
See [`LICENSE`](LICENSE).

## Repository

<https://github.com/stepan-a/continuo>

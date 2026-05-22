# dynare-ct

[![pipeline status](https://git.ithaca.fr/stepan/dynare-ct/badges/master/pipeline.svg)](https://git.ithaca.fr/stepan/dynare-ct/-/pipelines)

Continuous-time DSGE toolbox in the spirit of Dynare. A Python toolbox
for solving continuous-time macroeconomic models, with perfect-foresight
deterministic transitions, multi-revelation surprises, and permanent
parameter changes.

**Status: pre-alpha. No releases yet.** The pipeline runs end to end —
a `.mod` file solves to a path — but interfaces may still change. The
design lives in a separate document maintained outside this repository
for the time being.

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
- A CLI (`dynare-ct model.mod`) and a programmatic Python API
  (`import dynare_ct`).

Deferred: discretisation schemes beyond Crank–Nicolson (Radau,
Lobatto-IIIA), adaptive meshes, and HDF5/parquet output.

## Installation

No release yet — install from source:

```bash
git clone https://git.ithaca.fr/stepan/dynare-ct
cd dynare-ct
pip install -e .
```

Optional extras for the `Solution` conversion methods (`to_dataframe`,
`to_xarray`): `pip install -e ".[pandas,xarray,hdf5]"`.

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
import dynare_ct

model = dynare_ct.parse("rbc.mod")
sol = model.simul()                 # reads the simulate command

sol.t                               # time grid (numpy array)
sol["C"]                            # the consumption path
sol.K                               # attribute-style access

model.steady_state(exogenous={"z": 1.1})    # steady state under the new TFP
sol.to_dataframe()                  # pandas DataFrame (optional extra)
```

From the command line (writes `rbc.csv`):

```bash
dynare-ct rbc.mod
dynare-ct rbc.mod -o out.csv -T 100 -N 500   # override output / horizon / grid
```

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
pytest --cov=dynare_ct       # with a coverage report

ruff check src tests         # lint (as in CI)
ruff format --check src tests # formatting check (as in CI)
```

## License

Released into the public domain under the [Unlicense](https://unlicense.org/).
See [`LICENSE`](LICENSE).

## Repository

<https://git.ithaca.fr/stepan/dynare-ct>

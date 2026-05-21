# dynare-ct

[![pipeline status](https://git.ithaca.fr/stepan/dynare-ct/badges/master/pipeline.svg)](https://git.ithaca.fr/stepan/dynare-ct/-/pipelines)

Continuous-time DSGE toolbox in the spirit of Dynare. A Python toolbox
for solving continuous-time macroeconomic models, with perfect-foresight
deterministic transitions, multi-revelation surprises, and permanent
parameter changes.

**Status: pre-alpha. No releases yet.** The toolbox is in early
implementation; the design lives in a separate document maintained
outside this repository for the time being.

## Features (planned, v1)

- Continuous-time perfect-foresight solver via stacked collocation +
  Newton on a sparse two-point boundary value problem.
- Multi-segment information structures: anticipated, unanticipated,
  and sequentially-revised shocks; permanent parameter changes.
- Symbolic model representation, sparsity propagation, and Jacobian
  generation via CasADi; sparse linear solve via SciPy.
- Macroprocessor compatible with Dynare's `@#define`, `@#if`,
  `@#for`, `@#include` directives.
- A CLI (`dynare-ct model.mod`) and a programmatic Python API
  (`import dynare_ct`).

## Installation

```bash
pip install dynare-ct
```

(Optional extras: `pip install "dynare-ct[pandas,xarray,hdf5]"` for
the corresponding `Solution` conversion methods.)

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
nox -s tests            # tests across Python 3.11, 3.12 and 3.13
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

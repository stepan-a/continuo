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

## License

Released into the public domain under the [Unlicense](https://unlicense.org/).
See [`LICENSE`](LICENSE).

## Repository

<https://git.ithaca.fr/stepan/dynare-ct>

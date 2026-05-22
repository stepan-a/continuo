"""Command-line interface for continuo.

A thin wrapper over the programmatic API: parse a ``.mod`` file, run the
simulation, and write the solved path to a CSV file. Front-end and solver
errors are reported as clean messages rather than tracebacks.

    continuo model.mod                 # writes model.csv
    continuo model.mod -o out.csv -T 200 -N 400
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from continuo.api import parse
from continuo.codegen import CodegenError
from continuo.io.solution import Solution
from continuo.ir import IRError
from continuo.macro import MacroError
from continuo.parser.errors import LarkError
from continuo.solve import SolveError

__all__ = ["main"]

_ERRORS = (MacroError, LarkError, IRError, CodegenError, SolveError)


def main(argv: list[str] | None = None) -> int:
    """Entry point: returns 0 on success, 1 on a model/solver error."""
    args = _parse_args(argv)
    try:
        model = parse(args.model)
        solution = model.simul(horizon=args.horizon, intervals=args.intervals)
    except _ERRORS as exc:
        print(f"continuo: error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"continuo: cannot read {args.model!r}: {exc}", file=sys.stderr)
        return 1

    output = Path(args.output) if args.output else Path(args.model).with_suffix(".csv")
    _write_csv(solution, output)
    print(f"continuo: wrote {len(solution.t)} rows to {output}")
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="continuo",
        description="Solve a continuous-time perfect-foresight model and write the path to CSV.",
    )
    parser.add_argument("model", help="path to the .mod file")
    parser.add_argument("-o", "--output", help="output CSV file (default: <model>.csv)")
    parser.add_argument("-T", "--horizon", type=float, help="override the simulation horizon T")
    parser.add_argument("-N", "--intervals", type=int, help="override the grid resolution N")
    return parser.parse_args(argv)


def _write_csv(solution: Solution, output: Path) -> None:
    with open(output, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["t", *solution.names])
        for time, row in zip(solution.t, solution.path, strict=True):
            writer.writerow([time, *row])


if __name__ == "__main__":
    sys.exit(main())

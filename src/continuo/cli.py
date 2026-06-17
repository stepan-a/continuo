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
        solution = model.simul(
            horizon=args.horizon,
            intervals=args.intervals,
            scheme=args.scheme,
            order=args.order,
            adapt=args.adapt,
            monitor=args.monitor,
            solver=args.solver,
            steady_solver=args.steady_solver,
            steady_solver_options=_parse_options(args.steady_solver_option),
        )
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
    parser.add_argument(
        "--scheme",
        help="discretisation scheme, overriding the simulate directive "
        "(crank_nicolson, gauss, radau, lobatto_iiia)",
    )
    parser.add_argument(
        "--order",
        type=int,
        help="collocation order for a multi-stage scheme (e.g. --scheme radau --order 5)",
    )
    parser.add_argument(
        "--adapt",
        type=float,
        metavar="TOL",
        help="adaptively refine the grid to this error tolerance (e.g. --adapt 1e-4)",
    )
    parser.add_argument(
        "--monitor",
        help="error monitor driving --adapt (richardson, residual)",
    )
    parser.add_argument(
        "--solver",
        help="linear solver backend, overriding the simulate directive "
        "(e.g. auto, superlu, klu, klu-nobtf, umfpack, pardiso)",
    )
    parser.add_argument(
        "--steady-solver",
        help="nonlinear steady-state algorithm, overriding the steady directive "
        "(e.g. auto, newton, hybr, lm, kinsol, homotopy)",
    )
    parser.add_argument(
        "--steady-solver-option",
        action="append",
        metavar="KEY=VALUE",
        help="an option for the steady solver, repeatable "
        "(e.g. --steady-solver-option strategy=picard)",
    )
    return parser.parse_args(argv)


def _parse_options(items: list[str] | None) -> dict[str, object] | None:
    """Parse repeated ``KEY=VALUE`` flags into a dict, coercing numeric values."""
    if not items:
        return None
    options: dict[str, object] = {}
    for item in items:
        key, sep, raw = item.partition("=")
        if not sep or not key:
            raise SolveError(f"--steady-solver-option expects KEY=VALUE, got {item!r}")
        options[key] = _coerce(raw)
    return options


def _coerce(raw: str) -> object:
    """A solver-option value: int, then float, else the raw string."""
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw


def _write_csv(solution: Solution, output: Path) -> None:
    with open(output, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["t", *solution.names])
        for time, row in zip(solution.t, solution.path, strict=True):
            writer.writerow([time, *row])


if __name__ == "__main__":
    sys.exit(main())

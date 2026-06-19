#!/usr/bin/env python3
"""Benchmark the linear-solver backends across the example models.

Two modes:

- *end-to-end* (default) times the whole ``Model.simul()`` — what running an
  example actually costs — and measures the peak resident memory. Each
  (model, solver) pair runs in a fresh subprocess so the timings and the
  memory peak do not contaminate one another (notably, PARDISO pulls in MKL).
- *isolated* (``--micro``) times only the linear-solve phases on each model's
  real stacked Jacobian — ``analyze`` (symbolic, once per run), ``factor +
  solve`` (cold, a Newton step from scratch) and ``refactor + solve`` (warm,
  the dominant per-iteration cost once the analysis is amortised). This is
  where the backend differences show cleanly, free of the CasADi build.

Usage::

    python examples/benchmark_solvers.py              # end-to-end tables
    python examples/benchmark_solvers.py --micro       # isolated-solve tables
    python examples/benchmark_solvers.py --write       # update README + manual
    python examples/benchmark_solvers.py --micro --write
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import resource
import statistics
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent

# One canonical model per example folder (label -> path relative to examples/).
MODELS = [
    ("cagan", "cagan/cagan.mod"),
    ("dornbusch", "dornbusch/dornbusch.mod"),
    ("goodwin", "goodwin/goodwin.mod"),
    ("nk", "nk/nk_mild.mod"),
    ("nk-nonlinear", "nk-nonlinear/baseline.mod"),
    ("rbc", "rbc/rbc.mod"),
    ("solow", "solow/solow.mod"),
    ("tobinq", "tobinq/tobinq.mod"),
]

# Preferred display order; intersected with what is actually available.
SOLVER_ORDER = ["superlu", "klu", "klu-nobtf", "umfpack", "pardiso"]

START_MD, END_MD = "<!-- BENCHMARK:START -->", "<!-- BENCHMARK:END -->"
START_RST, END_RST = ".. BENCHMARK START", ".. BENCHMARK END"
START_MICRO, END_MICRO = ".. MICROBENCH START", ".. MICROBENCH END"


# ---------------------------------------------------------------------------
# workers: one (model, solver) measurement in an isolated process
# ---------------------------------------------------------------------------


def _worker_end2end(mod_path: str, solver: str, reps: int) -> dict:
    import continuo

    model = continuo.parse(mod_path)
    sol = model.simul(solver=solver)  # warm up (loads lazy backends, e.g. MKL)
    times_ms = []
    for _ in range(reps):
        t0 = time.perf_counter()
        model.simul(solver=solver)
        times_ms.append((time.perf_counter() - t0) * 1000.0)
    return {
        "ok": True,
        "median_ms": statistics.median(times_ms),
        "peak_rss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "n": int(sol.path.size),
    }


def _worker_micro(mod_path: str, solver_name: str, reps: int) -> dict:
    import numpy as np

    import continuo
    from continuo.solve import select_solver
    from continuo.solve.linsolve import SuperluSolver

    # Capture a representative stacked Jacobian by spying on a SuperLU solve.
    class Capture(SuperluSolver):
        def __init__(self) -> None:
            self.mats: list = []

        def analyze(self, a0):
            self.mats.append(a0.copy())
            return super().analyze(a0)

        def factor(self, a, sym):
            self.mats.append(a.copy())
            return super().factor(a, sym)

    cap = Capture()
    continuo.parse(mod_path).simul(solver=cap)
    a = cap.mats[-1]
    b = np.ones(a.shape[0])
    reps = max(reps, 50)  # the phases are microseconds; need enough samples

    def med(fn) -> float:
        for _ in range(3):  # warm up caches / workspace allocation
            fn()
        ts = []
        for _ in range(reps):
            t0 = time.perf_counter()
            fn()
            ts.append((time.perf_counter() - t0) * 1e6)  # microseconds
        return statistics.median(ts)

    solver = select_solver(solver_name)
    sym = solver.analyze(a)
    factor_solve_us = med(lambda: solver.solve(solver.factor(a, sym), b))
    state = {"num": solver.factor(a, sym)}

    def warm() -> None:
        state["num"] = solver.refactor(a, sym, state["num"])
        solver.solve(state["num"], b)

    refactor_solve_us = med(warm)
    return {
        "ok": True,
        "n": int(a.shape[0]),
        "factor_solve_us": factor_solve_us,
        "refactor_solve_us": refactor_solve_us,
    }


def _worker(mod_path: str, solver: str, reps: int, micro: bool) -> None:
    try:
        out = (_worker_micro if micro else _worker_end2end)(mod_path, solver, reps)
    except Exception as exc:  # noqa: BLE001 - report any backend failure as data
        out = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(out))


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------


def _measure(mod_path: Path, solver: str, reps: int, micro: bool) -> dict:
    cmd = [sys.executable, __file__, "--worker", str(mod_path), solver, "--reps", str(reps)]
    if micro:
        cmd.append("--micro")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    for line in reversed(proc.stdout.splitlines()):
        if line.strip().startswith("{"):
            return json.loads(line)
    return {"ok": False, "error": (proc.stderr.strip() or "no output")[:80]}


def _host() -> str:
    cpu = platform.processor() or platform.machine()
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    return f"{cpu}, {os.cpu_count()} cores, Python {platform.python_version()}"


def run(reps: int, micro: bool) -> dict:
    from continuo.solve import available_solvers

    solvers = [s for s in SOLVER_ORDER if s in available_solvers()]
    print(f"backends: {', '.join(solvers)}\n", file=sys.stderr)
    data: dict = {
        "solvers": solvers,
        "rows": [],
        "reps": reps,
        "host": _host(),
        "date": str(date.today()),
    }
    for label, rel in MODELS:
        mod_path = HERE / rel
        cells, size = {}, None
        for solver in solvers:
            res = _measure(mod_path, solver, reps, micro)
            cells[solver] = res
            if res.get("ok"):
                size = res["n"]
            key = "refactor_solve_us" if micro else "median_ms"
            tag = f"{res[key]:.1f}" if res.get("ok") else "FAIL"
            print(f"  {label:14s} {solver:10s} {tag}", file=sys.stderr)
        data["rows"].append({"label": label, "size": size, "cells": cells})
    return data


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------


def _us(res: dict, key: str) -> str:
    if not res.get("ok"):
        return "—"
    v = res[key]
    return f"{v:.0f}" if v >= 1000 else f"{v:.1f}"


def _cell(key: str):
    if key.endswith("_us"):
        return lambda res: _us(res, key)
    if key == "peak_rss_kb":
        return lambda res: f"{res['peak_rss_kb'] / 1024:.0f}" if res.get("ok") else "—"
    return lambda res: f"{res[key]:.1f}" if res.get("ok") else "—"


def _tables(micro: bool) -> list[tuple[str, str]]:
    if micro:
        return [
            ("factor + solve — cold, per Newton step (µs)", "factor_solve_us"),
            ("refactor + solve — warm, amortised analysis (µs)", "refactor_solve_us"),
        ]
    return [
        ("Wall-clock per solve (median, ms)", "median_ms"),
        ("Peak resident memory (MiB)", "peak_rss_kb"),
    ]


def _caption(data: dict, micro: bool) -> str:
    if micro:
        return (
            f"Median of {max(data['reps'], 50)} repetitions, timing only the linear-solve "
            f"phases on each model's real stacked Jacobian (the CasADi build is excluded). "
            f"`refactor + solve` is the dominant per-iteration cost once the analysis is "
            f"amortised. Measured {data['date']} on {data['host']}."
        )
    return (
        f"Median of {data['reps']} runs of end-to-end `Model.simul()` "
        f"(includes the CasADi build). Wall-clock in milliseconds; peak resident "
        f"memory in MiB (whole process — the Python/CasADi/SciPy baseline dominates, "
        f"and PARDISO loads MKL). Measured {data['date']} on {data['host']}."
    )


def _md(data: dict, micro: bool) -> str:
    solvers = data["solvers"]
    head = ["Model", "n", *solvers]
    sep = ["---", "---:", *["---:"] * len(solvers)]

    def table(title, key):
        cell = _cell(key)
        lines = [f"**{title}**", "", "| " + " | ".join(head) + " |", "| " + " | ".join(sep) + " |"]
        for r in data["rows"]:
            size = str(r["size"]) if r["size"] else "—"
            row = [r["label"], size, *[cell(r["cells"][s]) for s in solvers]]
            lines.append("| " + " | ".join(row) + " |")
        return "\n".join(lines)

    body = "\n\n".join(table(t, k) for t, k in _tables(micro))
    return body + f"\n\n_{_caption(data, micro)}_"


_README_NOTE = (
    "**Reading these:** the wall-clock above is *end-to-end* `Model.simul()`, "
    "dominated by the (solver-independent) CasADi build and residual/Jacobian "
    "evaluation — so on these small models the linear backend barely moves it. "
    "KLU's edge is in the linear solve itself: the isolated `refactor + solve` "
    "table (the warm per-Newton-step cost) shows it ~4–10× faster than SuperLU, a "
    "gap that grows with problem size and Newton iterations. PARDISO is far slower "
    "here only because MKL oversubscribes threads on these tiny systems — reserve "
    "it for large models. See the "
    "[Linear solvers](https://continuo.adjemian.eu/solvers.html) manual page for "
    "the full isolated tables."
)


def _readme_md(end_data: dict, micro_data: dict) -> str:
    """README block: the end-to-end tables, the isolated refactor+solve table from
    ``micro_data``, and a note on why the backend barely moves the end-to-end time."""
    solvers = end_data["solvers"]
    head = ["Model", "n", *solvers]
    sep = ["---", "---:", *["---:"] * len(solvers)]

    def table(data: dict, title: str, key: str) -> str:
        cell = _cell(key)
        lines = [f"**{title}**", "", "| " + " | ".join(head) + " |", "| " + " | ".join(sep) + " |"]
        for r in data["rows"]:
            size = str(r["size"]) if r["size"] else "—"
            row = [r["label"], size, *[cell(r["cells"][s]) for s in solvers]]
            lines.append("| " + " | ".join(row) + " |")
        return "\n".join(lines)

    blocks = [
        table(end_data, "Wall-clock per solve (median, ms)", "median_ms"),
        table(
            micro_data, "Isolated linear solve — refactor + solve, warm (µs)", "refactor_solve_us"
        ),
        table(end_data, "Peak resident memory (MiB)", "peak_rss_kb"),
        _README_NOTE,
    ]
    return "\n\n".join(blocks) + f"\n\n_{_caption(end_data, False)}_"


def _rst(data: dict, micro: bool) -> str:
    solvers = data["solvers"]
    head = ["Model", "n", *solvers]

    def list_table(title, key):
        cell = _cell(key)
        out = [f".. list-table:: {title}", "   :header-rows: 1", ""]

        def block(cells):
            return [f"   * - {cells[0]}"] + [f"     - {c}" for c in cells[1:]]

        out += block(head)
        for r in data["rows"]:
            size = str(r["size"]) if r["size"] else "—"
            out += block([r["label"], size, *[cell(r["cells"][s]) for s in solvers]])
        return "\n".join(out)

    body = "\n\n".join(list_table(t, k) for t, k in _tables(micro))
    return body + "\n\n" + _caption(data, micro).replace("`", "``")


def _inject(path: Path, start: str, end: str, body: str) -> bool:
    text = path.read_text()
    if start not in text or end not in text:
        print(f"  ! markers not found in {path}, skipped", file=sys.stderr)
        return False
    a, b = text.index(start) + len(start), text.index(end)
    path.write_text(text[:a] + "\n\n" + body + "\n\n" + text[b:])
    print(f"  updated {path.relative_to(REPO)}", file=sys.stderr)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark the linear-solver backends.")
    parser.add_argument("--worker", nargs=2, metavar=("MOD", "SOLVER"), help=argparse.SUPPRESS)
    parser.add_argument("--micro", action="store_true", help="time the isolated linear solve")
    parser.add_argument("--reps", type=int, default=5, help="repetitions per measurement")
    parser.add_argument(
        "--write", action="store_true", help="inject the tables into README + manual"
    )
    args = parser.parse_args()

    if args.worker:
        _worker(args.worker[0], args.worker[1], args.reps, args.micro)
        return

    data = run(args.reps, args.micro)
    print(_md(data, args.micro))
    if args.write:
        if args.micro:
            _inject(REPO / "doc/manual/solvers.rst", START_MICRO, END_MICRO, _rst(data, True))
        else:
            # The README pairs the end-to-end tables with the isolated
            # refactor+solve table, so measure both and regenerate every region
            # (README + the manual's end-to-end and micro tables) from one run.
            micro_data = run(args.reps, True)
            _inject(REPO / "README.md", START_MD, END_MD, _readme_md(data, micro_data))
            _inject(REPO / "doc/manual/solvers.rst", START_RST, END_RST, _rst(data, False))
            _inject(REPO / "doc/manual/solvers.rst", START_MICRO, END_MICRO, _rst(micro_data, True))


if __name__ == "__main__":
    main()

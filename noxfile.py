"""Automation sessions for continuo.

Run ``nox`` to execute the default sessions (lint and the testsuite on the
current interpreter), or ``nox -s <session>`` to pick one. Each session runs
in its own fresh virtual environment that nox builds and installs into.
"""

import nox

# Python versions the package supports (see pyproject.toml classifiers).
PYTHON_VERSIONS = ["3.13", "3.14"]

# Sessions run when ``nox`` is invoked with no ``-s`` argument. Tests default
# to the interpreter nox itself runs under; use ``nox -s tests`` to fan out
# across every version in PYTHON_VERSIONS (those interpreters must be present).
nox.options.sessions = ["lint", "tests"]

LINT_PATHS = ("src", "tests", "noxfile.py")


@nox.session
def lint(session):
    """Check style and formatting with ruff (no changes made)."""
    session.install("ruff>=0.5")
    session.run("ruff", "check", *LINT_PATHS)
    session.run("ruff", "format", "--check", *LINT_PATHS)


@nox.session
def fix(session):
    """Apply ruff autofixes and reformat in place."""
    session.install("ruff>=0.5")
    session.run("ruff", "check", "--fix", *LINT_PATHS)
    session.run("ruff", "format", *LINT_PATHS)


@nox.session(python=PYTHON_VERSIONS)
def tests(session):
    """Install the package with dev extras and run the testsuite."""
    # pandas / xarray are optional extras, installed so the Solution
    # conversion methods are exercised.
    session.install("-e", ".[dev,pandas,xarray]")
    session.run("pytest", "-q", "--tb=short", *session.posargs)


@nox.session
def coverage(session):
    """Run the testsuite with a coverage report."""
    session.install("-e", ".[dev]")
    session.run("pytest", "--cov=continuo", "--cov-report=term-missing", *session.posargs)

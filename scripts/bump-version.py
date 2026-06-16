#!/usr/bin/env python3
"""Bump the continuo package version across every place it is mentioned.

The single source of truth is ``pyproject.toml``. This helper reads the
current version from there and replaces it consistently. Two modes:

- a **release** bump (``X.Y.Z``) touches every version mention:
  ``pyproject.toml`` (``version``), ``doc/manual/conf.py`` (the ``release``
  fallback), ``README.md`` (the status line ``(vX.Y.Z, YYYY-MM-DD)`` and the
  release-wheel install URL) and ``CHANGELOG.md`` (a new ``## [X.Y.Z]`` entry
  + tag-link footnote);
- a **dev** bump (``--dev``) marks master as in-development *after* a
  release: it sets ``X.Y.(Z+1)-dev`` (or ``<version>-dev``) in
  ``pyproject.toml`` and ``conf.py`` only. ``README.md`` and ``CHANGELOG.md``
  track releases, not the dev cycle, so they are left untouched; the
  ``-dev`` suffix sorts *before* its release (``0.0.3-dev`` < ``0.0.3``), so
  the later release bump out of a dev version is a normal strict increase.

The runtime ``continuo.__version__`` is resolved dynamically via
``importlib.metadata`` and needs no edit; ``tests/test_smoke.py`` checks
it against ``importlib.metadata.version("continuo")`` rather than a
hard-coded literal, so it needs no edit either.

Usage::

    python scripts/bump-version.py 0.0.3          # release bump
    python scripts/bump-version.py 0.0.3 --check  # dry-run (no writes)
    python scripts/bump-version.py 0.0.3 --force  # allow downgrade
    python scripts/bump-version.py --dev          # post-release: -> X.Y.(Z+1)-dev
    python scripts/bump-version.py 0.1.0 --dev    # dev toward a chosen release: 0.1.0-dev

A typical cycle is: ``--dev`` right after tagging a release, then a release
bump out of that dev version when the next release is ready.

Once a release bump returns success: edit ``CHANGELOG.md`` to fill in the
new entry, then commit and tag (``git tag -a vX.Y.Z -m 'vX.Y.Z'``).
"""

from __future__ import annotations

import argparse
import datetime
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TODAY = datetime.date.today().isoformat()
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+([+-][0-9A-Za-z.+-]+)?$")

CHANGELOG_TEMPLATE = """\
## [{new}] — {date}

### Added

- TODO: user-visible additions.

### Changed

- TODO: changes to existing behaviour.

### Fixed

- TODO: bug fixes.

"""


def parse_version(v: str) -> tuple[int, int, int, int]:
    """Parse ``X.Y.Z[-pre]`` into a sortable key.

    A ``-pre`` suffix (e.g. ``-dev``) sorts *before* the matching ``X.Y.Z``
    release — the last tuple element is 0 for a pre-release and 1 for a
    release — so ``0.0.3-dev`` < ``0.0.3`` and a dev-to-release bump is a
    strict increase. ``+build`` metadata does not lower precedence.
    """
    core = re.split(r"[-+]", v, maxsplit=1)[0]
    major, minor, patch = (int(x) for x in core.split("."))
    is_prerelease = "-" in v
    return (major, minor, patch, 0 if is_prerelease else 1)


def next_patch_dev(current: str) -> str:
    """The ``X.Y.(Z+1)-dev`` version following a released ``X.Y.Z``."""
    major, minor, patch, rank = parse_version(current)
    if rank == 0:
        sys.exit(f"bump-version: current version {current!r} is already a dev version")
    return f"{major}.{minor}.{patch + 1}-dev"


def read_current_version() -> str:
    text = (ROOT / "pyproject.toml").read_text()
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not m:
        sys.exit("bump-version: pyproject.toml has no version field")
    return m.group(1)


def replace_once(path: Path, old: str, new: str, *, dry_run: bool) -> None:
    """Replace ``old`` by ``new`` in ``path``; require exactly one occurrence."""
    text = path.read_text()
    n = text.count(old)
    if n != 1:
        sys.exit(f"bump-version: {path.relative_to(ROOT)}: expected exactly 1 occurrence "
                 f"of {old!r}, found {n}")
    print(f"  {path.relative_to(ROOT)}: {old!r} -> {new!r}")
    if not dry_run:
        path.write_text(text.replace(old, new, 1))


_README_STATUS_RE = re.compile(r"\(v\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.+-]+)?, \d{4}-\d{2}-\d{2}\)")


def replace_readme_status(path: Path, new: str, *, dry_run: bool) -> None:
    """Replace the ``(vX.Y.Z, YYYY-MM-DD)`` status segment, whatever version it names.

    Matching the *existing* version (rather than the current one) lets a
    release bump run out of a dev version: the README still shows the prior
    release (it is not touched by a dev bump), and that is what gets replaced.
    """
    text = path.read_text()
    matches = _README_STATUS_RE.findall(text)
    if len(matches) != 1:
        sys.exit(f"bump-version: {path.relative_to(ROOT)}: expected exactly one "
                 f"'(vX.Y.Z, YYYY-MM-DD)' status, found {len(matches)}")
    replacement = f"(v{new}, {TODAY})"
    print(f"  {path.relative_to(ROOT)}: {matches[0]!r} -> {replacement!r}")
    if not dry_run:
        path.write_text(_README_STATUS_RE.sub(replacement, text))


# The GitHub-release wheel download URL(s) in the README install section. The
# version appears twice (the ``vX.Y.Z`` tag and the ``continuo-X.Y.Z`` wheel
# name); both move together. May appear more than once (plain + extras).
_README_WHEEL_RE = re.compile(
    r"releases/download/v\d+\.\d+\.\d+/continuo-\d+\.\d+\.\d+-py3-none-any\.whl"
)


def replace_readme_wheel(path: Path, new: str, *, dry_run: bool) -> None:
    """Point the README's release-wheel URL(s) at ``new`` (release bumps only)."""
    text = path.read_text()
    n = len(_README_WHEEL_RE.findall(text))
    replacement = f"releases/download/v{new}/continuo-{new}-py3-none-any.whl"
    if n == 0:
        print(f"  {path.relative_to(ROOT)}: no release-wheel URL found (skipped)")
        return
    print(f"  {path.relative_to(ROOT)}: {n} wheel URL(s) -> v{new}")
    if not dry_run:
        path.write_text(_README_WHEEL_RE.sub(replacement, text))


def insert_changelog_entry(path: Path, new: str, *, dry_run: bool) -> None:
    """Insert a new entry template at the top, and a matching tag-link footnote."""
    text = path.read_text()
    entry_match = re.search(r"^## \[", text, re.MULTILINE)
    if entry_match is None:
        sys.exit(f"bump-version: {path.relative_to(ROOT)}: no '## [...]' heading found")

    entry = CHANGELOG_TEMPLATE.format(new=new, date=TODAY)
    new_text = text[: entry_match.start()] + entry + text[entry_match.start() :]

    tag_link = f"[{new}]: https://github.com/stepan-a/continuo/releases/tag/v{new}\n"
    link_match = re.search(r"^\[\d", new_text, re.MULTILINE)
    if link_match is not None:
        new_text = new_text[: link_match.start()] + tag_link + new_text[link_match.start() :]
    else:
        new_text = new_text.rstrip() + "\n\n" + tag_link

    print(f"  {path.relative_to(ROOT)}: + '## [{new}] — {TODAY}' entry and tag link")
    if not dry_run:
        path.write_text(new_text)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Bump the continuo version.")
    ap.add_argument("version", nargs="?",
                    help="the new version (e.g. 0.0.3); optional with --dev")
    ap.add_argument("--dev", action="store_true",
                    help="post-release dev bump to X.Y.(Z+1)-dev (or <version>-dev); "
                         "writes pyproject.toml and conf.py only")
    ap.add_argument("--check", action="store_true",
                    help="dry-run: show what would change without writing")
    ap.add_argument("--force", action="store_true",
                    help="allow bumping to a lower or equal version")
    args = ap.parse_args(argv)

    current = read_current_version()

    if args.dev:
        if args.version is not None:
            if not re.fullmatch(r"\d+\.\d+\.\d+", args.version):
                sys.exit(f"bump-version: --dev target {args.version!r} must be X.Y.Z (no suffix)")
            new = f"{args.version}-dev"
        else:
            new = next_patch_dev(current)
    elif args.version is None:
        sys.exit("bump-version: a version is required (or use --dev)")
    else:
        new = args.version

    if not SEMVER_RE.match(new):
        sys.exit(f"bump-version: {new!r} is not a valid X.Y.Z[-pre] version")
    if current == new:
        sys.exit(f"bump-version: version is already {current}")
    if not args.force and parse_version(new) <= parse_version(current):
        sys.exit(f"bump-version: refusing to bump {current} -> {new} "
                 "(not strictly greater; use --force to override)")

    mode = "dev bump" if args.dev else "release"
    suffix = "  (dry run)" if args.check else ""
    print(f"Bumping {current} -> {new}  [{mode}]{suffix}\n")

    replace_once(ROOT / "pyproject.toml",
                 f'version = "{current}"', f'version = "{new}"',
                 dry_run=args.check)
    replace_once(ROOT / "doc/manual/conf.py",
                 f'release = "{current}"', f'release = "{new}"',
                 dry_run=args.check)
    # README and CHANGELOG track releases, not the dev cycle.
    if not args.dev:
        replace_readme_status(ROOT / "README.md", new, dry_run=args.check)
        replace_readme_wheel(ROOT / "README.md", new, dry_run=args.check)
        insert_changelog_entry(ROOT / "CHANGELOG.md", new, dry_run=args.check)

    print()
    if args.check:
        print("Dry run complete; re-run without --check to apply.")
    elif args.dev:
        print("Dev bump applied (pyproject.toml + conf.py).")
        print("Reinstall to refresh the reported version: pip install -e .")
    else:
        print("Next steps:")
        print(f"  1. Edit CHANGELOG.md to fill in the {new} entry.")
        print("  2. Verify: pip install -e . && pytest tests/test_smoke.py")
        print(f"  3. Commit: git commit -am 'Release v{new}.'")
        print(f"  4. Tag:    git tag -a v{new} -m 'v{new}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())

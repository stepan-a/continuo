#!/usr/bin/env python3
"""Bump the continuo package version across every place it is mentioned.

The single source of truth is ``pyproject.toml``. This helper reads the
current version from there and replaces it consistently in:

- ``pyproject.toml`` (``version = "X.Y.Z"``)
- ``tests/test_smoke.py`` (``__version__ == "X.Y.Z"``)
- ``doc/manual/conf.py`` (the ``release = "X.Y.Z"`` fallback)
- ``README.md`` (the status line ``(vX.Y.Z, YYYY-MM-DD)``)
- ``CHANGELOG.md`` — inserts a new ``## [X.Y.Z] — YYYY-MM-DD`` entry
  template at the top and a matching tag-link footnote.

The runtime ``continuo.__version__`` is resolved dynamically via
``importlib.metadata`` and needs no edit.

Usage::

    python scripts/bump-version.py 0.0.2          # apply the bump
    python scripts/bump-version.py 0.0.2 --check  # dry-run (no writes)
    python scripts/bump-version.py 0.0.2 --force  # allow downgrade

Once the script returns success: edit ``CHANGELOG.md`` to fill in the new
entry, then commit and tag (``git tag -a vX.Y.Z -m 'vX.Y.Z'``).
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


def parse_version(v: str) -> tuple[int, ...]:
    """Parse ``X.Y.Z`` (ignoring any pre-release suffix) into a tuple of ints."""
    core = re.split(r"[+-]", v, maxsplit=1)[0]
    return tuple(int(x) for x in core.split("."))


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


def replace_readme_status(path: Path, current: str, new: str, *, dry_run: bool) -> None:
    """Replace the ``(vX.Y.Z, YYYY-MM-DD)`` segment of the README status line."""
    text = path.read_text()
    pattern = re.compile(rf"\(v{re.escape(current)}, \d{{4}}-\d{{2}}-\d{{2}}\)")
    matches = pattern.findall(text)
    if len(matches) != 1:
        sys.exit(f"bump-version: {path.relative_to(ROOT)}: expected exactly one "
                 f"'(v{current}, YYYY-MM-DD)', found {len(matches)}")
    replacement = f"(v{new}, {TODAY})"
    print(f"  {path.relative_to(ROOT)}: {matches[0]!r} -> {replacement!r}")
    if not dry_run:
        path.write_text(pattern.sub(replacement, text))


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
    ap.add_argument("version", help="the new version (e.g. 0.0.2)")
    ap.add_argument("--check", action="store_true",
                    help="dry-run: show what would change without writing")
    ap.add_argument("--force", action="store_true",
                    help="allow bumping to a lower or equal version")
    args = ap.parse_args(argv)

    new = args.version
    if not SEMVER_RE.match(new):
        sys.exit(f"bump-version: {new!r} is not a valid X.Y.Z[-pre] version")

    current = read_current_version()
    if current == new:
        sys.exit(f"bump-version: version is already {current}")
    if not args.force and parse_version(new) <= parse_version(current):
        sys.exit(f"bump-version: refusing to bump {current} -> {new} "
                 "(not strictly greater; use --force to override)")

    suffix = "  (dry run)" if args.check else ""
    print(f"Bumping {current} -> {new}{suffix}\n")

    replace_once(ROOT / "pyproject.toml",
                 f'version = "{current}"', f'version = "{new}"',
                 dry_run=args.check)
    replace_once(ROOT / "tests/test_smoke.py",
                 f'continuo.__version__ == "{current}"',
                 f'continuo.__version__ == "{new}"',
                 dry_run=args.check)
    replace_once(ROOT / "doc/manual/conf.py",
                 f'release = "{current}"', f'release = "{new}"',
                 dry_run=args.check)
    replace_readme_status(ROOT / "README.md", current, new, dry_run=args.check)
    insert_changelog_entry(ROOT / "CHANGELOG.md", new, dry_run=args.check)

    print()
    if args.check:
        print("Dry run complete; re-run without --check to apply.")
    else:
        print("Next steps:")
        print(f"  1. Edit CHANGELOG.md to fill in the {new} entry.")
        print(f"  2. Verify: pip install -e . && pytest tests/test_smoke.py")
        print(f"  3. Commit: git commit -am 'Release v{new}.'")
        print(f"  4. Tag:    git tag -a v{new} -m 'v{new}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())

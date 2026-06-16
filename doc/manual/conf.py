"""Sphinx configuration for the continuo reference manual."""

from __future__ import annotations

import sys
from pathlib import Path

# Make the in-tree package importable for autodoc, without requiring
# `pip install -e .` first.
_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src"))

# -- Project information ----------------------------------------------------

project = "continuo"
author = "Stéphane Adjemian"
copyright = "2026, Stéphane Adjemian"

try:
    from continuo import __version__ as release
except Exception:  # pragma: no cover - fallback for un-installed builds
    release = "0.0.3-dev"
version = release

# -- General configuration --------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx_copybutton",
]

templates_path: list[str] = []
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# Napoleon — accept both Google and NumPy docstring styles.
napoleon_google_docstring = True
napoleon_numpy_docstring = True

# autodoc defaults: members included, source order, type hints in the
# description (rather than the signature) for readability.
autodoc_default_options = {
    "members": True,
    "show-inheritance": True,
}
autodoc_typehints = "description"
autodoc_member_order = "bysource"

# intersphinx
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
}

# Highlight ``.mod`` snippets as plain text — Pygments has no Dynare lexer
# and ``c``/``matlab`` introduce spurious "errors". ``text`` keeps blocks
# uncoloured but always valid.
highlight_language = "text"

# -- HTML output ------------------------------------------------------------

html_theme = "furo"
html_title = f"continuo {release}"
html_static_path: list[str] = []

# Two-track docs: ``master`` is published under ``/dev/`` and labels itself
# with a development version (e.g. ``0.0.3.dev0``); tagged releases are
# published at the site root. A banner points readers to the other track,
# chosen from the version string (PEP 440 dev releases contain ``dev``).
_STABLE_URL = "https://continuo.adjemian.eu/"
_DEV_URL = "https://continuo.adjemian.eu/dev/"
if "dev" in release:
    _announcement = (
        "You are reading the <strong>development</strong> documentation "
        f'(<code>master</code>). For the latest release, see the '
        f'<a href="{_STABLE_URL}">stable documentation</a>.'
    )
else:
    _announcement = (
        "You are reading the documentation for a released version. The "
        f'in-development version is in the <a href="{_DEV_URL}">development '
        "documentation</a>."
    )
html_theme_options = {"announcement": _announcement}

# Copy-button: strip the prompt characters when copying.
copybutton_prompt_text = r">>> |\.\.\. |\$ "
copybutton_prompt_is_regexp = True

# Master document (default since Sphinx 2.0, but explicit for clarity).
master_doc = "index"

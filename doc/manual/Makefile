# Minimal Sphinx Makefile for the continuo reference manual.
#
# Usage:
#   make html       # build HTML into _build/html
#   make linkcheck  # check external links
#   make clean      # remove _build
#   make            # show available targets

SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = .
BUILDDIR      = _build

help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile

# Catch-all: route every other target (html, clean, linkcheck, ...) to
# sphinx-build's -M dispatcher.
%:
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

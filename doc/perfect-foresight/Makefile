# The figure PDFs are generated from their Python scripts (continuo +
# matplotlib), not committed; rubber includes them. `make` builds them first.
FIGURES = btf_figure.pdf exp_convergence.pdf exp_adaptive.pdf exp_shocks.pdf

all: slides.pdf

slides.pdf: slides.tex $(FIGURES)
	rubber --shell-escape --pdf slides && rubber --clean slides

%.pdf: %.py
	python $<

clean:
	rubber --clean slides

.PHONY: all clean

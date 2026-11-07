# COCO-Bench paper (R3.7). `make` regenerates every number, table and figure from committed data,
# then typesets paper.pdf; `make check` fails if any committed generated file differs from the
# data or a number is typed into the text. Needs Python 3 with matplotlib, and a TeX distribution
# with IEEEtran (latexmk + pdflatex + bibtex).
PY ?= python3

.PHONY: all generated check clean arxiv

all: paper.pdf

generated:
	$(PY) -P scripts/paper_numbers.py
	$(PY) -P scripts/tables.py
	$(PY) -P scripts/figures.py
	$(PY) -P scripts/lint_tex.py

paper.pdf: generated main.tex refs.bib sections/*.tex
	latexmk -pdf -interaction=nonstopmode -halt-on-error -jobname=paper main.tex

check:
	$(PY) -P scripts/paper_numbers.py --check
	$(PY) -P scripts/tables.py --check
	$(PY) -P scripts/figures.py --check
	$(PY) -P scripts/lint_tex.py

# the arXiv source bundle (prepared, never submitted here: submitting is Gautham's call)
arxiv: paper.pdf
	rm -rf arxiv && mkdir -p arxiv/sections arxiv/generated arxiv/figures
	cp main.tex refs.bib paper.bbl arxiv/
	cp sections/*.tex arxiv/sections/
	cp generated/*.tex arxiv/generated/
	cp figures/*.pdf arxiv/figures/
	cd arxiv && tar czf ../coco-bench-arxiv.tar.gz .

clean:
	latexmk -C -jobname=paper main.tex || true
	rm -rf arxiv coco-bench-arxiv.tar.gz

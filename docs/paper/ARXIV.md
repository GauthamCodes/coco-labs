# The arXiv source bundle — prepared, never submitted here

**Submitting (arXiv or any venue) is Gautham's call** (R3 prompt §0.5). This file says how to make the
bundle and what to check first. Author: "Gautham", no affiliation (Gautham, 2026-11-07).

## Making the PDF and the bundle

- **In CI (no TeX needed locally):** the `Paper` workflow (`.github/workflows/paper.yml`) runs
  `make check` and `make` on every pull request into main and every push to main, and uploads the PDF as the
  artifact **`coco-bench-paper`** (90 days). Download it from the run's page, or
  `gh run download <run-id> -n coco-bench-paper`.
- **Locally (needs a TeX distribution with IEEEtran, latexmk, pdflatex and bibtex):**

  ```bash
  make -C docs/paper              # numbers, tables, figures from committed data; lint; paper.pdf
  make -C docs/paper check        # fails if anything generated differs from the data, or a number is typed
  make -C docs/paper arxiv        # docs/paper/coco-bench-arxiv.tar.gz (after `make`)
  ```

  This laptop has no TeX (downloading a TeX engine was refused by the session's permission check), so the
  bundle is made where TeX exists: on a machine with TeX Live, or by adding an `arxiv` step to the Paper
  workflow.

## What goes in the bundle (`make arxiv`)

| file | why |
| --- | --- |
| `main.tex` | the paper |
| `sections/*.tex` | its sections |
| `generated/*.tex` | `numbers.tex` (every number, a macro naming its source), `suites_table.tex`, `results.tex` when present |
| `figures/*.pdf` | the figures, drawn from `generated/fig_*.json` |
| `refs.bib` and `paper.bbl` | the bibliography (arXiv compiles with the `.bbl`) |

Not in the bundle: the scripts and data (they are in the repository the paper cites; the appendix says how to
regenerate everything).

## Before submitting — checklist

1. **The numbers are final:** `make -C docs/paper check` passes on the commit being submitted, and the Paper
   workflow is green on that commit. The experiments section must contain R3's baselines and the model-vs-ROS 2
   gap (`generated/results.tex`), not only the R2/R3 Part A results.
2. **Citations:** every `refs.bib` entry has its record in `CITATIONS.md`; none is marked `[CHECK]`. Re-check
   any entry added since 2026-11-07.
3. **Venue:** pick one in `VENUES.md`. Every date there came from a web search on 2026-11-07, and the ones marked
   `[CHECK]` are not confirmed by an official page. Open the official page and re-check the date and format
   before deciding; RSS 2027's extended-abstract deadline (4 December 2026) is the nearest.
4. **Format:** the venue's page limit and template (the draft uses IEEEtran conference); the reproducibility
   appendix may count against the limit.
5. **Claims:** MODEL vs STACK labels in every result; "no physical robot" stated; negative results (Theta\*'s
   0/5) kept; the s086 discrepancy stated as unresolved.
6. **Links:** the "Reproduce this paper" link opens on the deployed site and its digest check passes (it needs
   R3 deployed).
7. **Licence:** the repository is Apache-2.0; arXiv's licence choice for the paper is Gautham's.
8. **Decision:** Gautham reads the PDF and decides whether, where and when to submit.

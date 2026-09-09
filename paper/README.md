# Paper Package

This folder contains the manuscript source and the public distribution files.

## Contents

- `IEEE_Distributed_AI_Ensemble.pdf` - compiled manuscript
- `IEEE_Distributed_AI_Ensemble.docx` - Word version
- `IEEE_Distributed_AI_Ensemble.tex` - LaTeX source
- `IEEE_Distributed_AI_Ensemble.txt` - plain-text version
- `references.bib` - Bibliography entries
- `figures/` - PNG charts embedded in the paper
- `tables/` - Auto-generated LaTeX tables from benchmark outputs
- `overleaf/` - Mirrored Overleaf upload package

## Public Distribution Policy

The manuscript is published openly in this repository as plain `.pdf`, `.docx`, `.tex`, and `.txt` files.
No access gate, password, or encryption is applied.

## Rebuild the Manuscript

```bash
cd paper
pdflatex IEEE_Distributed_AI_Ensemble.tex
bibtex IEEE_Distributed_AI_Ensemble
pdflatex IEEE_Distributed_AI_Ensemble.tex
pdflatex IEEE_Distributed_AI_Ensemble.tex
```

## Regenerate Figures and Tables

```bash
cd /root/Distributed-AI
/root/distributed_ai/.venv/bin/python scripts/generate_visual_assets.py
```

## Data Provenance

Primary benchmark artifacts:

- `../artifacts/benchmark_runs/run_20260226_193331/`
- `../artifacts/optimization_runs/`

These inputs are used to generate:

- aggregate table (`tables/aggregate_strategy_results.tex`)
- per-benchmark table (`tables/per_benchmark_results.tex`)
- significance table (`tables/significance_highlights.tex`)
- chart assets in `figures/`

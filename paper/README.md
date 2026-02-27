# IEEE / Overleaf Paper Package

This folder contains the full manuscript package for conference-style submission.

## Contents

- `IEEE_Distributed_AI_Ensemble.tex` - Main IEEE manuscript source
- `IEEE_Distributed_AI_Ensemble.pdf` - Compiled manuscript PDF
- `IEEE_Distributed_AI_Ensemble.docx` - Word export of the manuscript
- `IEEE_Distributed_AI_Ensemble.txt` - Plain-text export of the manuscript
- `references.bib` - Bibliography entries
- `figures/` - PNG charts embedded in the paper
- `tables/` - Auto-generated LaTeX tables from benchmark outputs
- `overleaf/` - Upload-ready Overleaf package

## Build Locally

```bash
cd paper
pdflatex IEEE_Distributed_AI_Ensemble.tex
bibtex IEEE_Distributed_AI_Ensemble
pdflatex IEEE_Distributed_AI_Ensemble.tex
pdflatex IEEE_Distributed_AI_Ensemble.tex
```

Output file:

- `paper/IEEE_Distributed_AI_Ensemble.pdf`

Optional export formats:

```bash
cd paper
pandoc IEEE_Distributed_AI_Ensemble.tex -s -o IEEE_Distributed_AI_Ensemble.docx
pandoc IEEE_Distributed_AI_Ensemble.tex -t plain -o IEEE_Distributed_AI_Ensemble.txt
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

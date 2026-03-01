# Protected Paper Package

This folder contains the supporting manuscript assets and the encrypted public distribution package.

## Contents

- `IEEE_Distributed_AI_Ensemble_Protected.tar.gpg` - AES-encrypted manuscript package
- `PAPER_ACCESS_INSTRUCTIONS.txt` - Decryption guide for authorized readers
- `references.bib` - Bibliography entries
- `figures/` - PNG charts embedded in the paper
- `tables/` - Auto-generated LaTeX tables from benchmark outputs
- `overleaf/` - Supporting Overleaf assets plus the encrypted manuscript package

## Public Distribution Policy

The public branch does not ship the manuscript as plain `.pdf`, `.docx`, `.tex`, or `.txt` files.
Only the encrypted package is distributed here.

Authorized readers must:

1. Download `IEEE_Distributed_AI_Ensemble_Protected.tar.gpg`
2. Follow the steps in `PAPER_ACCESS_INSTRUCTIONS.txt`
3. Enter the approved password to decrypt and extract the package

## Open the Protected Package

```bash
cd paper
gpg --decrypt --output IEEE_Distributed_AI_Ensemble_Protected.tar \
  IEEE_Distributed_AI_Ensemble_Protected.tar.gpg
tar -xf IEEE_Distributed_AI_Ensemble_Protected.tar
```

## Regenerate Figures and Tables

```bash
cd /root/Distributed-AI
/root/distributed_ai/.venv/bin/python scripts/generate_visual_assets.py
```

## Private Editing Note

If you need to edit or rebuild the manuscript, use your private local backup of the plain source files.
Those editable manuscript files are intentionally excluded from the public branch.

## Data Provenance

Primary benchmark artifacts:

- `../artifacts/benchmark_runs/run_20260226_193331/`
- `../artifacts/optimization_runs/`

These inputs are used to generate:

- aggregate table (`tables/aggregate_strategy_results.tex`)
- per-benchmark table (`tables/per_benchmark_results.tex`)
- significance table (`tables/significance_highlights.tex`)
- chart assets in `figures/`

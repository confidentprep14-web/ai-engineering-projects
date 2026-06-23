# Data Exploration

EDA pipeline for the UCI Adult Income dataset. Outputs a Markdown data quality report.

> Part of [Path 3 — ML Engineering on AWS](https://confidentprep.com/paths/path-3) on Confident Prep — see the full curriculum and how this project fits in.

## Prerequisites

- Python 3.11+
- No AWS credentials needed

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
mkdir -p data && curl -o data/adult.data \
  "https://archive.ics.uci.edu/ml/machine-learning-databases/adult/adult.data"
python src/main.py --data data/adult.data --output report.md
```

## What you get

`report.md` with:
- Class balance (and imbalance ratio)
- Per-feature statistics (numeric: mean/std/min/median/max; categorical: top values)
- Missing value counts per column
- Pearson correlation matrix (numeric features)
- List of columns flagged for imputation strategy (>20% missing)

## Change the missing threshold

```bash
python src/main.py --data data/adult.data --output report.md --missing-threshold 0.05
```

## Tests

```bash
pytest tests/ -v
```

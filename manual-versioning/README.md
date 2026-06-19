# Manual Versioning

Train three XGBoost variants, track results with timestamped folders and JSON metadata.

## Prerequisites

- Python 3.11+
- No AWS credentials needed

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
mkdir -p data && curl -o data/adult.data \
  "https://archive.ics.uci.edu/ml/machine-learning-databases/adult/adult.data"
python src/train_all.py
```

## Train a single variant

```bash
python src/train_variant.py --max-depth 5 --learning-rate 0.05 --data data/adult.data
```

## Compare all runs

```bash
python src/compare.py
```

## Output

Each run creates `models/run_{timestamp}/model.xgb` and `models/run_{timestamp}/metadata.json`.

`compare.py` prints a table and marks the best run by val_AUC.

## Tests

```bash
pytest tests/ -v
```

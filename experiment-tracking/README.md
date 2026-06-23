# Experiment Tracking

MLflow-instrumented XGBoost training with hyperparameter sweep, model registry, and inference.

> Part of [Path 3 — ML Engineering on AWS](https://confidentprep.com/paths/path-3) on Confident Prep — see the full curriculum and how this project fits in.

## Prerequisites

- Python 3.11+
- No AWS credentials needed

## Quick start

**Terminal 1 — start MLflow server:**
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python src/start_server.py
```

**Terminal 2 — run experiments:**
```bash
source .venv/bin/activate
mkdir -p data && curl -o data/adult.data \
  "https://archive.ics.uci.edu/ml/machine-learning-databases/adult/adult.data"
python src/sweep.py
python src/select_best.py
python src/load_and_infer.py
```

## View experiments

Open `http://localhost:5000` in your browser.

## Run a single experiment

```bash
python src/train_with_mlflow.py --max-depth 5 --learning-rate 0.05
```

## Tests

```bash
pytest tests/ -v
```

Note: tests use a temp MLflow tracking directory, not the local server.

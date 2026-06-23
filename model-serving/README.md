# P3-07 — Model Serving

Deploy a real-time SageMaker endpoint, benchmark latency (p50/p95/p99), and measure cold start.

> Part of [Path 3 — ML Engineering on AWS](https://confidentprep.com/paths/path-3) on Confident Prep — see the full curriculum and how this project fits in.

## WARNING

This project creates a SageMaker endpoint that costs ~$0.056/hour (ml.t2.medium).
Run `bash scripts/teardown.sh` immediately after you finish testing.

## Prerequisites

- Python 3.11+
- AWS credentials configured
- `experiment-tracking/` completed: MLflow registry has a "production" alias
- MLflow server running at http://localhost:5000 (or `MLFLOW_TRACKING_URI` pointed at the registry)

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in S3_BUCKET, SAGEMAKER_ROLE_ARN

python src/deploy.py
python src/benchmark.py --endpoint-name $(cat .endpoint-name)
python src/cost_logger.py
```

## Cold start test

```bash
python src/cold_start.py --endpoint-name $(cat .endpoint-name)
```

## TEARDOWN (run this before closing your session)

```bash
bash scripts/teardown.sh
```

## Tests

```bash
pytest tests/ -v
```

6/6 passing. Tests do not make AWS API calls (mocked).

## Status: AWS-touching steps unverified — needs AWS credentials

`deploy.py`'s `create_sagemaker_model`/`create_endpoint_config`/`create_endpoint`,
`benchmark.py`'s real `invoke_endpoint` calls, `cold_start.py`'s delete/recreate cycle,
and `cost_logger.py`'s use against a real `.endpoint-created-at` timestamp are all
implemented per spec but were never executed against real AWS in this environment —
there is no AWS account here. Same precedent as `local-to-sagemaker/` and
`batch-inference/`.

**What *was* verified for real, with zero AWS:** `inference.py`'s `model_fn` and
`predict_fn` were run against `experiment-tracking/`'s actual local MLflow registry
(not a fake model) — loading the real "production"-aliased model via
`mlflow.xgboost.load_model("models:/adult-income-xgboost@production")`, saving it as
`model.xgb`, and round-tripping held-out test rows from `data/adult.data` through
`model_fn` + `predict_fn` reproduced **val_auc: 0.9289** against the real `y_test`
labels — the same number `experiment-tracking` and `batch-inference` report for this
exact production model. This confirms the inference handlers are genuinely correct
against the real registered model, not just unit-tested against a toy model fit on
random data.

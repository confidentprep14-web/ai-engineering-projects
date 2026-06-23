# P3-08 — A/B Testing

Deploy two model variants behind one SageMaker endpoint. Shift traffic. Pick the winner.

> Part of [Path 3 — ML Engineering on AWS](https://confidentprep.com/paths/path-3) on Confident Prep — see the full curriculum and how this project fits in.

## WARNING

This project creates a SageMaker endpoint with TWO instances (~$0.11/hr total).
Run `bash scripts/teardown.sh` immediately after you finish testing.

## Prerequisites

- Python 3.11+
- AWS credentials configured
- p3-05 completed: MLflow registry has "production" alias
- MLflow server running at http://localhost:5000

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in S3_BUCKET, SAGEMAKER_ROLE_ARN

python src/prepare_variants.py
python src/deploy_ab.py
python src/invoke_traffic.py --endpoint-name $(cat .endpoint-name) --n-requests 1000
python src/evaluate_winner.py --endpoint-name $(cat .endpoint-name)
python src/promote_winner.py
```

## Traffic shifting

```bash
# 50/50 split
python src/shift_traffic.py --current-weight 5 --challenger-weight 5

# Full challenger rollout
python src/shift_traffic.py --current-weight 0 --challenger-weight 10
```

## TEARDOWN

```bash
bash scripts/teardown.sh
```

## Tests

```bash
pytest tests/ -v
```

5/5 passing. Tests do not make AWS API calls (mocked).

## Status: AWS-touching steps unverified — needs AWS credentials

`deploy_ab.py`'s `create_variant_model`/`create_ab_endpoint_config`/`create_and_wait_endpoint`,
`invoke_traffic.py`'s real `invoke_endpoint` calls and variant-routing observation,
`shift_traffic.py`'s real `update_endpoint_weights_and_capacities` call, and
`evaluate_winner.py`'s real CloudWatch `get_metric_statistics` fetch are all implemented
per spec but were never executed against real AWS in this environment — there is no AWS
account here. Same precedent as `model-serving/` and `batch-inference/`.

**What *was* verified for real, with zero AWS:**

- `load_current_model` loaded the actual "production"-aliased model from
  `experiment-tracking/`'s real local MLflow registry — `mlflow.xgboost.load_model("models:/adult-income-xgboost@production")`
  reproduced the same **val_auc: 0.9289** that `experiment-tracking`, `batch-inference`,
  and `model-serving` all report for this exact model.
- `train_challenger` trained a real XGBClassifier on `data/adult.data` with the exact
  hyperparameters from `.env.example` (`max_depth=7, learning_rate=0.05, n_estimators=200`)
  using the same 80/20 split (`random_state=42`) as p3-01/p3-05/p3-06/p3-07. The real
  challenger scored **val_AUC: 0.9294** against the held-out set.
- `apply_decision_rule(challenger_auc=0.9294, baseline_auc=0.9289, threshold=0.01)` was run
  for real on these two genuine numbers. Delta = **+0.0005**, well under the 0.01 threshold,
  so the rule's actual output is **keep current** — the deeper/slower-learning-rate
  challenger is not meaningfully better than production on this dataset, and the quantitative
  rule correctly says don't ship it.
- `package_and_upload`'s packaging logic (model.tar.gz creation, minus the S3 upload) was
  run for both variants. The two resulting tar.gz files have different SHA-256 hashes, and
  loading both back through `inference.py`'s `model_fn`/`predict_fn` produces different
  `predict_proba` values on the same sample row — confirming the two variants are genuinely
  distinct artifacts, not copies of each other.
- `promote_to_production`'s actual `mlflow.register_model()` + `set_registered_model_alias()`
  calls were exercised against a **throwaway temp MLflow registry** (`file:///tmp/p3_08_verify_registry`,
  seeded with a copy of the real production model, then deleted after the test) — never
  against the shared `experiment-tracking/mlruns` registry that `batch-inference`,
  `model-serving`, and future projects depend on. The "challenger" branch correctly
  registered a new version and moved the "production" alias to it; the "current" branch
  correctly left the alias untouched. The shared registry's "production" alias still points
  at version 1 (val_auc 0.9289), unmodified by this verification.

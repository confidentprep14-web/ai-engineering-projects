# P3-06 — Batch Inference

SageMaker Batch Transform: offline predictions on held-out test set. No persistent endpoint.

## Prerequisites

- Python 3.11+
- AWS credentials configured
- p3-05 completed: "production" alias in MLflow registry
- MLflow server running at http://localhost:5000 (from p3-05)

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in S3_BUCKET and SAGEMAKER_ROLE_ARN

# Package and upload model
python src/prepare_model.py

# Run batch predictions
python src/run_batch.py

# Compare costs
python src/cost_compare.py --batch-duration-minutes 8 --instance-type ml.m5.large \
  --estimated-rpm 100 --endpoint-hourly-cost 0.056
```

**Status: AWS-touching steps unverified — needs AWS credentials.** `prepare_model.py`
and `run_batch.py` are implemented per spec but `upload_to_s3`, `create_sagemaker_model`,
and `run_transform_job` were never executed against real AWS in this environment — same
precedent as `local-to-sagemaker/` and `aws-lambda-deploy/`.

**What *was* verified for real, with zero AWS:** `load_model_from_registry` and
`create_model_tar` were run against p3-05's actual local MLflow registry (not a fake
model) — loading the real "production"-aliased model and round-tripping it through
`inference.py`'s `model_fn`/`predict_fn` reproduced the exact same **val_auc: 0.9289**
p3-05 reported for its best run, confirming the registry-load → packaging → inference
chain is correct end-to-end. (Note: the spec's "9,769 rows" holdout figure doesn't match
this preprocessing pipeline's actual output — both this project and p3-05 use the same
`dropna()`-based cleaning, which yields 6,033 holdout rows, not 9,769. The val_auc match
confirms the 6,033-row split is the correct, consistent one.)

## IMPORTANT: teardown after use

```bash
bash scripts/teardown.sh
```

Deletes: SageMaker Model resource, S3 input prefix, S3 output prefix.

## Tests

```bash
pytest tests/ -v
```

5/5 passing. Tests do not make AWS API calls.

# P3-10 — Model Monitoring

SageMaker Model Monitor: data capture, baseline, drift injection, violation reports.

## Prerequisites

- Python 3.11+
- AWS credentials configured
- p3-07 endpoint running (check: `aws sagemaker describe-endpoint --endpoint-name p3-07-adult-income-endpoint`)

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in S3_BUCKET, SAGEMAKER_ROLE_ARN, ENDPOINT_NAME

# Enable data capture
python src/enable_capture.py --endpoint-name p3-07-adult-income-endpoint

# Compute baseline from training data
python src/compute_baseline.py --data data/adult.data

# Schedule hourly monitoring
python src/schedule_monitoring.py --endpoint-name p3-07-adult-income-endpoint

# Inject synthetic drift
python src/inject_drift.py --endpoint-name p3-07-adult-income-endpoint --n-requests 100

# Wait up to 1 hour for monitoring to run, then read violations
python src/read_violations.py
```

## TEARDOWN

```bash
bash scripts/teardown.sh
```

## Run tests (no AWS needed)

```bash
pytest tests/ -v
```

6/6 passing. Tests use a real fixture (`fixtures/sample_violation_report.json`) and the
real `data/adult.data` training file — no AWS credentials needed, no AWS calls mocked
behind the scenes because none of the tested logic makes one.

## Status: AWS-touching steps unverified — needs AWS credentials and a running endpoint

`enable_capture.py`'s real `update_endpoint`/waiter calls, `compute_baseline.py`'s real S3
upload + `suggest_baseline()` SageMaker job, `schedule_monitoring.py`'s real
`create_monitoring_schedule` call, `inject_drift.py`'s real `send_drifted_requests`
(actual `invoke_endpoint` calls), and `read_violations.py`'s real S3 fetch are all
implemented per spec but were never executed against real AWS in this environment —
there is no AWS account, no S3 bucket, and no running SageMaker endpoint here. Same
precedent as `model-serving/`, `ab-testing/`, and `performance-reporting/`.

**What *was* verified for real, with zero AWS:**

- `compute_feature_stats` and `create_drifted_row` have zero AWS dependency — pure
  pandas/numpy over the real `data/adult.data` file (same 32,561-row UCI Adult dataset
  used across this entire Path 3 sequence). Run for real: `age` mean/std came back
  **38.4379 / 13.1347** (close to the spec's illustrative ~38.6 / ~13.6 — the spec's
  numbers are approximate). `create_drifted_row(feature_stats, std_multiplier=2.0)`
  produced a real drifted `age` value of **64.7072**, which is exactly
  `mean + 2*std` (38.4379 + 2×13.1347 = 64.7073 — confirmed to 4 decimal places) and sits
  more than 2 standard deviations above the training mean — the statistical tail region
  the KS test is built to catch, even though it falls inside the raw `[17, 90]` age range
  (drift detection flags *distribution shift*, not out-of-bounds values). The returned row
  has shape **(104,)**, matching the real one-hot-encoded feature width of this dataset
  after the standard p3-01 preprocessing (column names, strip, `?`→NaN drop, `get_dummies`).
- `parse_violation`/`parse_monitoring_report` have zero AWS dependency — pure JSON parsing.
  Run for real against the real `fixtures/sample_violation_report.json`:
  `python src/read_violations.py --local-file fixtures/sample_violation_report.json` printed

  ```
  Model Monitor Report — 2 violation(s) found
  ========================================
  Feature 'age': distribution shifted significantly.
    Test: non-parametric significance test
    Expected p-value > 0.05, observed p-value = 0.0008
    Interpretation: The distribution of 'age' in recent traffic is unlikely to match training data.
  ----------------------------------------
  Feature 'hours-per-week': distribution shifted significantly.
    Test: non-parametric significance test
    Expected p-value > 0.05, observed p-value = 0.0013
    Interpretation: The distribution of 'hours-per-week' in recent traffic is unlikely to match training data.
  ```

  which matches the spec's example format exactly.
- `enable_capture.py`'s `build_data_capture_config` (the DataCaptureConfig-building logic
  `test_enable_capture_config_has_correct_s3_path` checks) is pure dict construction with
  no AWS call required to verify shape. Run for real:
  `build_data_capture_config("s3://my-ml-training-bucket/p3-10/capture/", capture_percentage=100)`
  returned a dict with `DestinationS3Uri == "s3://my-ml-training-bucket/p3-10/capture/"`
  (starts with `s3://`) and `InitialSamplingPercentage == 100`, exactly as required.

## What drift detection catches and misses

See GUIDE.md for an honest assessment.

# P3-09 — Performance Reporting

Weekly model performance report: CloudWatch metrics + live evaluation + MLflow baseline.

> Part of [Path 3 — ML Engineering on AWS](https://confidentprep.com/paths/path-3) on Confident Prep — see the full curriculum and how this project fits in.

## Prerequisites

- Python 3.11+
- AWS credentials configured (or use --dry-run for local testing)
- p3-05 MLflow server running with "production" alias registered
- Optional: p3-07 endpoint running for live evaluation

## Quick start (dry run — no AWS)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python src/main.py --dry-run --output output/report.md
cat output/report.md
```

## Run against a live endpoint

```bash
cp .env.example .env  # fill in endpoint name and region
python src/main.py --endpoint-name p3-07-adult-income-endpoint --days 7 --output output/report.md
```

## Set up as a cron job

```cron
0 9 * * 1  cd /path/to/performance-reporting && .venv/bin/python src/main.py --output output/report-$(date +%Y%m%d).md >> logs/cron.log 2>&1
```

Runs every Monday at 9am. Output file is date-stamped.

## Tests

```bash
pytest tests/ -v
```

6/6 passing. Tests use mocked AWS responses — no credentials needed.

## Status: AWS-touching steps unverified — needs AWS credentials and a running endpoint

`cloudwatch_fetcher.py`'s real `get_metric_statistics` call and `live_evaluator.py`'s real
`invoke_endpoint` calls against a live SageMaker endpoint are implemented per spec but were
never executed against real AWS in this environment — there is no AWS account and no running
endpoint here. Same precedent as `model-serving/` and `ab-testing/`.

**What *was* verified for real, with zero AWS:**

- The `--dry-run` path — the one most learners and this build actually exercise — is fully
  real and AWS-free by design. `python src/main.py --dry-run --output output/report.md` was
  run for real, with zero AWS credentials, and produced a complete `report.md` containing
  every required section (`## Summary`, `## Endpoint Health`, `## Live Evaluation`,
  `## Baseline`, `## Recommendation`) populated from the fixture data.
- `baseline_fetcher.get_baseline_from_registry` has zero AWS dependency — it is a pure MLflow
  registry read. It was pointed at `experiment-tracking/`'s real local MLflow registry
  (`mlflow.set_tracking_uri("file:///.../experiment-tracking/mlruns")`) and called for real:
  `get_baseline_from_registry("adult-income-xgboost", "production")` returned
  **val_auc: 0.9289** and a real `run_id` (`82dc30dd49a54d9e8690049d40ec9069`) — the same
  number `experiment-tracking`, `batch-inference`, `model-serving`, and `ab-testing` all
  report for this exact production model. This confirms the registry-read logic is genuinely
  correct against production data, not just unit-tested with a mock. The read-only registry
  was not modified.
- `reporter.compute_delta` and `reporter.generate_weekly_report` were exercised end-to-end
  using that real baseline (0.9289) combined with a synthetic "current" AUC of 0.90 — a
  believable degradation scenario. The real run produced delta **-0.0289 (regression)** and
  status **WARNING**, with the recommendation text correctly flagging the threshold breach.
  This confirms the report-generation logic with one real number in the mix, not purely
  synthetic data.

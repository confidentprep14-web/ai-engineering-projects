# Guide — P3-09 Performance Reporting

## Why performance reporting matters

Deployed models degrade silently. The data distribution shifts, the world changes, and your
model keeps returning predictions — just increasingly wrong ones. Without a regular performance
check, you find out about degradation from users or from downstream business metrics, not from
your ML system.

## The three data sources

**CloudWatch:** Tells you about endpoint health — how many requests, what latency, how many errors.
It does NOT tell you if the model is accurate. An endpoint can have 0 errors and 100% wrong predictions.

**Live evaluation:** You send your held-out test set (or a sample) to the actual endpoint and
compare predictions to ground truth. This tells you actual current accuracy, but requires having
ground-truth labels available — which is not always the case.

**MLflow baseline:** The AUC logged when you registered the "production" model. This is your
reference point. The delta between live AUC and baseline AUC is the signal you monitor.

## The status thresholds

The ±0.02 AUC threshold is illustrative. In production, calibrate it to:
- Historical AUC variation between training runs (if your model naturally varies ±0.01, a 0.02 drop may not be meaningful)
- Business impact (for fraud detection, a 0.01 AUC drop may be critical; for content ranking, it may not be)

This project's real verification run is a concrete example of the threshold doing its job:
combining the real production baseline (val_AUC 0.9289, fetched live from
`experiment-tracking/`'s MLflow registry) with a synthetic current AUC of 0.90 produced a delta
of -0.0289 — comfortably past the ±0.02 threshold — and the status correctly flipped to
WARNING with a recommendation to investigate drift or retrain. The dry-run fixtures, by
contrast, use a smaller -0.012 AUC delta that stays inside the threshold and reports OK — the
two runs together show both branches of the status logic exercised against real code paths.

## Cron safety requirements

The script must:
- Exit with code 0 on success, non-zero on failure (cron can alert on non-zero exit)
- Write output to a file (not just stdout — cron captures stdout/stderr, but file output is more durable)
- Print nothing sensitive to stdout (logs go to CloudWatch or a file, not a user terminal)
- Handle all exceptions at the top level — never leave a partial JSON or broken Markdown file

## Verifying without AWS

`baseline_fetcher.get_baseline_from_registry` has no AWS dependency at all — it only needs a
local MLflow registry. That means the "is the model still as good as production" question can
be partially answered for real with zero AWS account: fetch the real registered baseline,
combine it with a live-evaluation AUC (real or synthetic), and run it through the actual
`compute_delta` / `generate_weekly_report` logic. This project did exactly that against
`experiment-tracking/`'s real registry, reading (never writing) `val_auc: 0.9289` and
`run_id: 82dc30dd49a54d9e8690049d40ec9069`. What stays unverified is purely the AWS plumbing:
whether `cloudwatch_fetcher.fetch_endpoint_metrics`'s real `get_metric_statistics` call returns
the expected shape against a live endpoint, and whether `live_evaluator.evaluate_endpoint`'s
real `invoke_endpoint` calls correctly parse production response payloads. Both are
code-complete per spec and covered by the `--dry-run` fixture path, just never run against a
real AWS account in this environment.

## Interview framing

"I treat model monitoring as a regular reporting job: pull CloudWatch health metrics, evaluate
live accuracy on a sample of the test set, compare to the registered baseline, and surface the
delta as a status. The script runs as a cron job every week — so AUC degradation is caught
in days, not months. I've verified the registry-read and report-generation logic end-to-end
against a real MLflow baseline (val_AUC 0.9289) rather than only mocking it, which is the part
of this pipeline I can actually trust without a live AWS endpoint in front of me."

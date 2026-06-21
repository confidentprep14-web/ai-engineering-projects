# Weekly Model Performance Report
Generated: 2026-06-21 02:42 UTC
Endpoint: p3-07-adult-income-endpoint
Period: Last 7 days

## Summary

| Metric | Current | Baseline | Delta |
|---|---|---|---|
| AUC | 0.8710 | 0.8830 | -0.0120 |
| Accuracy | 0.8610 | 0.8720 | -0.0110 |

**Status:** OK
- OK: current AUC within 0.02 of baseline
- WARNING: current AUC drops more than 0.02 below baseline
- UNKNOWN: baseline or live metrics not available

## Endpoint Health (CloudWatch)

| Metric | Value |
|---|---|
| Invocations (last 7d) | 842 |
| Avg Model Latency | 23.4 ms |
| Error Count | 3 |
| Error Rate | 0.36% |

## Live Evaluation

Evaluated 200 samples from held-out test set.
- AUC: 0.8710
- Accuracy: 0.8610

## Baseline (MLflow Registry)

- Model: adult-income-xgboost @ production
- Run ID: fixture_run
- Baseline val_AUC: 0.8830

## Recommendation

Live AUC is within the expected range of the registered baseline. No action needed -- continue routine weekly monitoring.

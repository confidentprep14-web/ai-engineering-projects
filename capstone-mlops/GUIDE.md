# Guide — P3-12 Capstone

## What you have built

You now have a complete MLOps system:

**Data path:** New training data → S3 → trigger → preprocess → train → evaluate → deploy
**Serving path:** Users → endpoint → predictions → data capture → drift monitoring → alarm
**Reporting path:** Weekly report → live AUC + CloudWatch health → baseline comparison

This is the feedback loop that makes a deployed ML model maintainable at scale.

## What is missing (production concerns not covered)

**Authentication:** This system has no authentication on the endpoint. In production you would
use API Gateway + IAM authentication in front of the SageMaker endpoint.

**Multi-region:** Everything runs in one region. A production system may need regional endpoints
for latency and redundancy.

**Rollback:** If the newly deployed model turns out to be worse in production, there is no
automated rollback. You would need to keep the previous `EndpointConfig` and switch back.

**Data labeling:** The performance report assumes you have labeled test data. In production,
you may not get labels for weeks (e.g., churn prediction — you find out if a user churned
30 days later). This requires a separate labeling pipeline.

**Feature store:** All preprocessing is re-done at training time and inference time independently.
A feature store (SageMaker Feature Store) would centralize this.

## The cost structure you should internalize

| Cost driver | Control lever |
|---|---|
| Endpoint idle time | Delete when not in use; use auto-scaling down to 0 (not available on SageMaker — use Lambda instead for low-traffic) |
| Training job instance size | Use ml.m5.large for small datasets; only scale up when training time is the bottleneck |
| Monitoring job frequency | Hourly is the SageMaker minimum; daily is usually sufficient for slow-moving production data |
| Data storage | S3 capture data accumulates; set a lifecycle policy to expire after 90 days |

## The interview narrative

You now have a story that covers:
- Local training (p3-01) → managed training (p3-01 SageMaker)
- EDA (p3-02) → feature engineering (p3-03) → experiment tracking (p3-05)
- Batch vs real-time inference (p3-06 vs p3-07)
- A/B testing (p3-08) → performance reporting (p3-09) → drift monitoring (p3-10)
- Automated retraining (p3-11) → integrated system (p3-12)

The narrative: "I've built an end-to-end ML system on AWS, from data preprocessing through
automated retraining. I understand the trade-offs at each layer — when to use batch vs
real-time inference, how to detect and respond to drift, and how to implement safe model
rollouts with A/B testing and automated deployment gates."

## What this project actually verifies (and what it doesn't)

Be honest about this when you talk about it in an interview: `verify_components.py`,
`end_to_end_test.py`, and `cost_dashboard.py` are AWS orchestration glue, not algorithms.
There is no decision rule or drift math here comparable to `retraining-pipeline`'s
`evaluate_improvement` or `model-monitoring`'s baseline statistics — the substantive logic
already lives in those earlier projects. What this capstone adds is the wiring and the
operational surface: one command to check liveness, one command to exercise the whole loop,
one command to see what it costs, and a runbook for when any piece of it breaks. That is a
legitimate and commonly underbuilt skill — most teams have the individual components but no
single place that proves they work together — but it is a different skill from "I wrote the
math," and a good interview answer says so directly instead of overclaiming.

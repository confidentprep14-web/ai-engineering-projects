# Guide — P3-07 Model Serving

## What you will observe

**p50 latency** (median): most requests see this. For a simple XGBoost model on ml.t2.medium,
expect 10-30ms.

**p95 latency:** 5% of requests take longer than this. This is typically the SLA target for
production ML services.

**p99 latency:** 1% of requests take longer. This is where you see GC pauses, CPU contention,
and cold inference paths.

**Cold start:** Creating a fresh endpoint takes 3-5 minutes for SageMaker to provision the
instance and load your container. The first inference after creation runs the container cold —
model loading happens on the first `model_fn` call, adding 1-2 seconds.

## Latency vs throughput

`benchmark.py` sends invocations sequentially (one at a time). This measures latency, not
throughput. If you want throughput, you send parallel requests — but that requires multiple
threads and a larger instance. Sequential benchmarking is the right method for SLA validation.

## Why ml.t2.medium for learning

ml.t2.medium ($0.056/hr) is the cheapest SageMaker inference instance. A simple XGBoost
model fits easily in 4GB RAM. For production, you would use ml.c5.large or larger, or
enable auto-scaling. For this project, t2.medium lets you learn without running up a bill.

## The cost of always-on

An endpoint running 24/7 on ml.t2.medium costs $0.056 × 24 × 30 = $40.32/month.
For 10,000 predictions/day at 100 RPM, you would need the endpoint running 10,000/100/60 = 1.7 hours/day
= $0.095/day = $2.85/month. Batch inference for the same volume costs ~$0.02/day. The tradeoff:
real-time latency vs batch economics.

## Verifying the inference chain without AWS

`model_fn`/`input_fn`/`predict_fn`/`output_fn` in `inference.py` have no AWS dependency at
all — they're plain Python functions that operate on a loaded XGBoost model and numpy arrays.
That means the entire inference chain can be verified for real against any live MLflow
registry on disk, by pointing `MLFLOW_TRACKING_URI` at a `file://` path. This project's
"production" alias is `experiment-tracking/`'s actual best XGBoost model, so loading it with
`mlflow.xgboost.load_model("models:/adult-income-xgboost@production")`, saving it as
`model.xgb`, and round-tripping real held-out rows from `data/adult.data` through
`model_fn` + `predict_fn` gives a genuine end-to-end correctness check with zero AWS account
needed. The reproduced `val_auc: 0.9289` matching `experiment-tracking`'s and
`batch-inference`'s reported number for this same production model is the proof — what
remains unverified is only the AWS plumbing around it (endpoint creation, real network
invocations, cold start timing), not the inference logic itself.

## Interview framing

"I can deploy a SageMaker endpoint, benchmark its p50/p95/p99 latency distribution, and
measure cold start time. I know that p95 is the typical SLA target, that sequential
benchmarking measures latency not throughput, and that endpoint cost is always-on — so the
batch vs real-time decision is driven by latency requirements, not just volume."

# Guide — P3-06 Batch Inference

## Batch Transform vs real-time endpoint

**Batch Transform** is a job: you give it an S3 path of inputs, it spins up instances,
generates predictions, writes outputs to S3, and terminates. You pay only for the duration
of the job. No idle cost.

**Real-time endpoint** is a persistent server: always running, always billable (even when
no requests come in), and returns predictions in <1 second.

**Choose batch when:** predictions can be computed hours in advance (e.g., overnight churn
scores, next-day recommendations). Choose real-time when users are waiting for a response.

## Why model.tar.gz must have files at the root

SageMaker's XGBoost container expects `model.xgb` and `inference.py` at the top level of the
archive (not inside a subdirectory). If you accidentally do `tar czf model.tar.gz mydir/`, the
container will not find your model. `create_model_tar` adds both files with `arcname=` set to
just the basename, then re-opens the archive and asserts both names are present — always
verify with `tar tzf model.tar.gz` before uploading if you change this code.

## The split_type="Line" setting

`split_type="Line"` tells SageMaker Batch Transform to send one CSV row per request to
your `input_fn`. Without this, it sends the entire file as one request — which works but
uses more memory and is harder to parallelize. With it, SageMaker can fan out rows across
multiple instances if you scale up.

## Reading batch output

The output file is named `{input_filename}.out` in your S3 output prefix. Each line is
one prediction (the output of your `output_fn`). The ordering matches the input rows.

## Verifying the registry-load chain without AWS

Everything up to "upload to S3" is plain Python — no AWS dependency. That means
`load_model_from_registry` and `create_model_tar` can be verified for real against any
live MLflow registry on disk, by pointing `MLFLOW_TRACKING_URI` at a `file://` path. This
project's "production" alias is p3-05's actual best XGBoost model, so this gives a real
end-to-end correctness check (registry load → tar.gz packaging → `model_fn`/`predict_fn`
round-trip) with zero AWS account needed — the reproduced `val_auc: 0.9289` matching
p3-05's reported number is the proof.

## Cost math worked out

At ml.m5.large ($0.115/hr), a 10-minute job costs $0.019.
At ml.t2.medium ($0.056/hr) for a real-time endpoint serving 100 RPM for an equivalent
volume of 9,773 predictions: 9,773 / 100 / 60 = 1.6 hours = $0.09.
Batch wins here. Flip the RPM to 10,000 and real-time becomes $0.0009 — batch loses.

## Interview framing

"I use SageMaker Batch Transform for workloads where predictions can be generated offline
in bulk — it's significantly cheaper than a persistent endpoint for infrequent or large-volume
jobs where sub-second latency isn't required."

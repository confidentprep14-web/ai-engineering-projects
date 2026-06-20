# Guide — Experiment Tracking

## What MLflow gives you vs the JSON folder

| Capability | p3-04 (JSON files) | p3-05 (MLflow) |
|---|---|---|
| Search by metric | Scan all JSON files manually | `mlflow.search_runs(order_by=["metrics.val_auc DESC"])` |
| Compare runs visually | Not possible | MLflow UI with parallel coordinates |
| Link metric to code version | Not possible | MLflow auto-logs git SHA |
| Load model for inference | Hardcode the model path | `mlflow.pyfunc.load_model("models:/name@production")` |
| Promote model to production | Copy file, update a config | Set alias in registry |

## What `mlflow.log_metric(..., step=i)` does

Logging with a step creates a time series in MLflow. When you log `val_logloss` at each
boosting round, the MLflow UI shows you the learning curve — you can see if the model
is still improving or has plateaued.

## The Model Registry vs artifact storage

The model artifact (the XGBoost `.xgb` file) lives in the artifact store (your `./mlruns`
directory or S3 in production). The Model Registry is a metadata layer on top: it tracks
versions, aliases (`production`, `staging`, `archived`), and descriptions.

When you `load_model("models:/adult-income-xgboost@production")`, MLflow looks up the
registry to find which artifact version has the `production` alias, then retrieves it.
You never hard-code a file path.

## The alias pattern

Using aliases (`production`, `staging`) instead of version numbers decouples your inference
code from the registry history. When you promote a new model to production, you move the
alias — the inference code does not change.

## Interview framing

"I use MLflow for experiment tracking — every run logs its hyperparameters, per-epoch metrics,
and model artifact. I can compare 5 runs in one query, register the winner with a semantic alias,
and load it by alias at inference time. That's the workflow I'd use on a team."

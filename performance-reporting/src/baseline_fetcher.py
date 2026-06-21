"""Fetch the registered "production" model's baseline metrics from MLflow.

This is the reference point the weekly report compares live performance
against. It is a pure registry read -- no model artifact is downloaded or
loaded, so this module has zero dependency on xgboost (unlike the projects
that actually serve predictions, e.g. model-serving/ and ab-testing/).
"""
import mlflow
from mlflow import MlflowClient


def get_baseline_from_registry(model_name: str, alias: str = "production") -> dict:
    """Look up the model version registered under `alias` for `model_name`
    and return its logged val_auc/val_accuracy metrics.

    Returns:
        {
            "val_auc": float | None,
            "val_accuracy": float | None,
            "run_id": str | None,
            "model_name": str,
            "alias": str,
        }

    Never raises -- if the alias doesn't exist, or the run is missing the
    val_auc/val_accuracy metric, the corresponding field(s) come back None
    and the caller decides how to report "baseline unavailable".
    """
    client = MlflowClient()

    try:
        version = client.get_model_version_by_alias(model_name, alias)
    except Exception:
        return {
            "val_auc": None,
            "val_accuracy": None,
            "run_id": None,
            "model_name": model_name,
            "alias": alias,
        }

    run_id = version.run_id

    try:
        run = mlflow.get_run(run_id)
        metrics = run.data.metrics
    except Exception:
        metrics = {}

    return {
        "val_auc": metrics.get("val_auc"),
        "val_accuracy": metrics.get("val_accuracy"),
        "run_id": run_id,
        "model_name": model_name,
        "alias": alias,
    }

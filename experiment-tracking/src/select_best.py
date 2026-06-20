"""Find the best run in an experiment by val_auc and register it to the
Model Registry with a semantic alias.
"""
import argparse
import os

import mlflow
import pandas as pd
from dotenv import load_dotenv
from mlflow import MlflowClient

load_dotenv()


def find_best_run(experiment_name: str, metric: str = "val_auc") -> pd.DataFrame:
    """Return the top run (by metric, descending) as a single-row DataFrame."""
    runs = mlflow.search_runs(
        experiment_names=[experiment_name],
        order_by=[f"metrics.{metric} DESC"],
    )
    if runs.empty:
        raise ValueError("No runs found in experiment. Run sweep.py first.")
    return runs.iloc[[0]]


def register_best_model(best_run: pd.Series, model_name: str, alias: str = "production") -> str:
    """Register the best run's model artifact and set the given alias.

    Returns the registered model version number as a string.
    """
    run_id = best_run["run_id"]
    model_uri = f"runs:/{run_id}/model"

    model_version = mlflow.register_model(model_uri, model_name)

    client = MlflowClient()
    client.set_registered_model_alias(model_name, alias, model_version.version)

    return str(model_version.version)


def main():
    parser = argparse.ArgumentParser(description="Select best sweep run and register it")
    parser.add_argument(
        "--experiment-name",
        type=str,
        default=os.getenv("MLFLOW_EXPERIMENT_NAME", "adult-income-sweep"),
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default=os.getenv("MLFLOW_MODEL_NAME", "adult-income-xgboost"),
    )
    args = parser.parse_args()

    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))

    best_run_df = find_best_run(args.experiment_name)
    best_run = best_run_df.iloc[0]

    version = register_best_model(best_run, args.model_name, alias="production")

    run_id = best_run["run_id"]
    val_auc = best_run["metrics.val_auc"]
    print(f"Best run: {run_id}")
    print(f"val_auc: {val_auc:.4f}")
    print(f'Registered as: {args.model_name} version {version} with alias "production"')


if __name__ == "__main__":
    main()

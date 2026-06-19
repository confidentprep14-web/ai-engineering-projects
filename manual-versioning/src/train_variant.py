"""Train one XGBoost variant on the UCI Adult dataset and save it to a
timestamped run directory under models/, alongside a metadata.json that
describes exactly what produced it.

This is "manual versioning": no database, no server, just a folder per run.
"""

import argparse
import json
import os
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score
from xgboost import XGBClassifier

COLUMN_NAMES = [
    "age",
    "workclass",
    "fnlwgt",
    "education",
    "education-num",
    "marital-status",
    "occupation",
    "relationship",
    "race",
    "sex",
    "capital-gain",
    "capital-loss",
    "hours-per-week",
    "native-country",
    "income",
]


def generate_run_id() -> str:
    """Return a unique-per-second run id like 'run_20250616_143022'."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"run_{timestamp}"


def load_and_prepare(data_path: str) -> tuple:
    """Load the UCI Adult dataset and split it into train/test sets.

    Same loading logic as the p3-01 project: assign column names, strip
    whitespace, replace '?' with NaN, drop NaN rows, one-hot encode features,
    and target-encode income as a 0/1 label.
    """
    if not os.path.exists(data_path):
        raise FileNotFoundError(f"Data file not found: {data_path}")

    df = pd.read_csv(data_path, header=None, names=COLUMN_NAMES, skipinitialspace=True)

    string_columns = df.select_dtypes(include="object").columns
    for col in string_columns:
        df[col] = df[col].astype(str).str.strip()

    df = df.replace("?", np.nan)
    df = df.dropna()

    y = df["income"].str.contains(">50K").astype(int)
    X = df.drop(columns=["income"])
    X = pd.get_dummies(X)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    return X_train, X_test, y_train, y_test


def train_and_evaluate(X_train, y_train, X_test, y_test, hyperparams: dict) -> dict:
    """Fit an XGBClassifier with hyperparams and return model + metrics."""
    model = XGBClassifier(use_label_encoder=False, eval_metric="logloss", **hyperparams)

    start = time.perf_counter()
    model.fit(X_train, y_train)
    train_time_seconds = time.perf_counter() - start

    val_auc = roc_auc_score(y_test, model.predict_proba(X_test)[:, 1])

    return {
        "model": model,
        "val_auc": float(val_auc),
        "train_time_seconds": float(train_time_seconds),
    }


def save_run(model, run_id: str, hyperparams: dict, metrics: dict, models_dir: str) -> dict:
    """Save model + metadata.json to {models_dir}/{run_id}/ and return the metadata dict."""
    run_dir = os.path.join(models_dir, run_id)
    os.makedirs(run_dir, exist_ok=True)

    model_path = os.path.join(run_dir, "model.xgb")
    model.save_model(model_path)

    metadata = {
        "run_id": run_id,
        "hyperparams": hyperparams,
        "metrics": {
            "val_auc": round(float(metrics["val_auc"]), 4),
            "train_time_seconds": round(float(metrics["train_time_seconds"]), 2),
        },
        "model_path": model_path,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    metadata_path = os.path.join(run_dir, "metadata.json")
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    return metadata


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(
        description="Train one XGBoost variant on the UCI Adult dataset"
    )
    parser.add_argument("--max-depth", type=int, required=True)
    parser.add_argument("--learning-rate", type=float, required=True)
    parser.add_argument("--n-estimators", type=int, default=100)
    parser.add_argument("--data", type=str, default="data/adult.data")
    parser.add_argument("--models-dir", type=str, default="models/")
    args = parser.parse_args(argv)

    hyperparams = {
        "max_depth": args.max_depth,
        "learning_rate": args.learning_rate,
        "n_estimators": args.n_estimators,
    }

    X_train, X_test, y_train, y_test = load_and_prepare(args.data)
    result = train_and_evaluate(X_train, y_train, X_test, y_test, hyperparams)

    run_id = generate_run_id()
    metadata = save_run(
        result["model"],
        run_id,
        hyperparams,
        {"val_auc": result["val_auc"], "train_time_seconds": result["train_time_seconds"]},
        args.models_dir,
    )

    print(
        f"Run {run_id} complete. val_auc={metadata['metrics']['val_auc']:.4f}, "
        f"train_time={metadata['metrics']['train_time_seconds']:.2f}s"
    )
    print(f"Saved to {metadata['model_path']}")

    return metadata


if __name__ == "__main__":
    main()

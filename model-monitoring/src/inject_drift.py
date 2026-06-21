"""Inject synthetic data drift by sending requests to the endpoint with
numeric features shifted to mean + N*std -- values the training data (and
therefore the baseline) has never seen at this magnitude.

This is the "make the alarm fire" half of the project: compute_baseline.py
establishes what's normal, this script deliberately sends abnormal data so
the next monitoring run has something to flag.
"""
import argparse
import os

import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

COLUMN_NAMES = [
    "age", "workclass", "fnlwgt", "education", "education-num",
    "marital-status", "occupation", "relationship", "race", "sex",
    "capital-gain", "capital-loss", "hours-per-week", "native-country",
    "income",
]


def _load_features(data_path: str) -> pd.DataFrame:
    """Load and preprocess the UCI Adult data into the feature frame (no
    target column), same preprocessing as p3-01/compute_baseline.py.
    """
    df = pd.read_csv(data_path, header=None, names=COLUMN_NAMES, skipinitialspace=True)

    string_columns = df.select_dtypes(include="object").columns
    for col in string_columns:
        df[col] = df[col].astype(str).str.strip()

    df = df.replace("?", np.nan)
    df = df.dropna()

    return df.drop(columns=["income"])


def compute_feature_stats(data_path: str) -> dict:
    """Load the UCI Adult training data and compute mean/std for each
    numeric (pre-one-hot-encoding) feature.

    Returns {feature_name: {"mean": float, "std": float}} for numeric
    features only.
    """
    X = _load_features(data_path)
    numeric_cols = X.select_dtypes(include=[np.number]).columns

    return {
        col: {"mean": float(X[col].mean()), "std": float(X[col].std())}
        for col in numeric_cols
    }


def create_drifted_row(feature_stats: dict, std_multiplier: float = 2.0, data_path: str = "data/adult.data") -> np.ndarray:
    """Build a single drifted feature row in the same column order as the
    one-hot-encoded feature space used by the model.

    For each numeric feature: set value to mean + std_multiplier * std.
    For each categorical feature: use the most common (mode) value from
    training data -- no drift injected for categoricals, only numerics.

    Returns a 1D numpy array.
    """
    X = _load_features(data_path)
    numeric_cols = set(X.select_dtypes(include=[np.number]).columns)
    categorical_cols = [c for c in X.columns if c not in numeric_cols]

    row = {}
    for col in X.columns:
        if col in feature_stats:
            stats = feature_stats[col]
            row[col] = stats["mean"] + std_multiplier * stats["std"]
        else:
            row[col] = X[col].mean() if col in numeric_cols else None

    for col in categorical_cols:
        if row[col] is None:
            row[col] = X[col].mode().iloc[0]

    row_df = pd.DataFrame([row], columns=X.columns)
    X_ohe = pd.get_dummies(X)
    row_ohe = pd.get_dummies(row_df)
    row_ohe = row_ohe.reindex(columns=X_ohe.columns, fill_value=0)

    return row_ohe.iloc[0].to_numpy(dtype=float)


def send_drifted_requests(endpoint_name: str, drifted_row: np.ndarray, n_requests: int) -> dict:
    """Send n_requests invocations of drifted_row (as CSV) to the endpoint.

    Returns {"sent": int, "succeeded": int, "failed": int}.
    """
    import boto3

    runtime = boto3.client("sagemaker-runtime")
    csv_payload = ",".join(str(v) for v in drifted_row)

    succeeded = 0
    failed = 0
    for _ in range(n_requests):
        try:
            runtime.invoke_endpoint(
                EndpointName=endpoint_name,
                ContentType="text/csv",
                Body=csv_payload,
            )
            succeeded += 1
        except Exception:
            failed += 1

    return {"sent": n_requests, "succeeded": succeeded, "failed": failed}


def main():
    parser = argparse.ArgumentParser(description="Inject synthetic drift into a SageMaker endpoint")
    parser.add_argument("--endpoint-name", type=str, default=os.getenv("ENDPOINT_NAME"))
    parser.add_argument("--n-requests", type=int, default=100)
    parser.add_argument("--data", type=str, default="data/adult.data")
    args = parser.parse_args()

    if not args.endpoint_name:
        raise ValueError("--endpoint-name is required (or set ENDPOINT_NAME in .env)")

    multiplier = float(os.getenv("DRIFT_STD_MULTIPLIER", "2.0"))

    feature_stats = compute_feature_stats(args.data)
    drifted_row = create_drifted_row(feature_stats, std_multiplier=multiplier, data_path=args.data)

    print(f"Injecting drift: {args.n_requests} requests with features at mean + {multiplier}*std")

    X = _load_features(args.data)
    for feature, stats in feature_stats.items():
        lo, hi = X[feature].min(), X[feature].max()
        injected_value = stats["mean"] + multiplier * stats["std"]
        print(f"{feature}: expected range [{lo:.0f}, {hi:.0f}], injecting {injected_value:.1f}")

    result = send_drifted_requests(args.endpoint_name, drifted_row, args.n_requests)
    print(f"Drift injection complete. {result['succeeded']}/{result['sent']} requests succeeded.")


if __name__ == "__main__":
    main()

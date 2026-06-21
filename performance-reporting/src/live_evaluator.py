"""Evaluate a live SageMaker endpoint's accuracy/AUC against a sample of the
held-out test set.

CloudWatch (cloudwatch_fetcher.py) tells you the endpoint is up and answering
requests quickly -- it says nothing about whether the answers are *correct*.
This module sends real test rows through the endpoint and compares the
endpoint's predictions to ground-truth labels, which is the only way to
detect silent accuracy drift.
"""
from io import StringIO

import boto3
import pandas as pd
from sklearn.metrics import accuracy_score, roc_auc_score

COLUMN_NAMES = [
    "age", "workclass", "fnlwgt", "education", "education-num",
    "marital-status", "occupation", "relationship", "race", "sex",
    "capital-gain", "capital-loss", "hours-per-week", "native-country",
    "income",
]


def _load_test_split(test_data_path: str):
    """Load the UCI Adult dataset and reproduce the same preprocessing and
    80/20 train/test split (random_state=42) used in training (p3-01/p3-05),
    so the held-out rows here line up with the model's actual held-out set.

    Returns (X_test, y_test) as a DataFrame/Series pair.
    """
    df = pd.read_csv(test_data_path, header=None, names=COLUMN_NAMES, skipinitialspace=True)

    df = df.apply(lambda col: col.str.strip() if col.dtype == "object" else col)
    df = df.replace("?", pd.NA)
    df = df.dropna()

    y = (df["income"].str.strip(".") == ">50K").astype(int)
    X = df.drop(columns=["income"])
    X = pd.get_dummies(X)

    n = len(X)
    split_idx = int(n * 0.8)

    # Same shuffle as training: random_state=42, then take the last 20%.
    shuffled_idx = X.sample(frac=1.0, random_state=42).index
    test_idx = shuffled_idx[split_idx:]

    X_test = X.loc[test_idx]
    y_test = y.loc[test_idx]
    return X_test, y_test


def evaluate_endpoint(endpoint_name: str, test_data_path: str, sample_size: int = 200) -> dict:
    """Send `sample_size` rows from the held-out test set to the live
    endpoint and compute accuracy/AUC against ground truth.

    Returns:
        {
            "accuracy": float | None,
            "auc": float | None,
            "n_samples": int,
            "endpoint_name": str,
        }

    Raises:
        RuntimeError: if every single invocation fails (endpoint likely down).
    """
    X_test, y_test = _load_test_split(test_data_path)

    available = len(X_test)
    n = min(sample_size, available)

    sample_X = X_test.sample(n=n, random_state=42)
    sample_y = y_test.loc[sample_X.index]

    runtime = boto3.client("sagemaker-runtime")

    y_true = []
    y_pred = []
    y_prob = []
    failed = 0

    for idx, row in sample_X.iterrows():
        payload = ",".join(str(v) for v in row.values)
        try:
            response = runtime.invoke_endpoint(
                EndpointName=endpoint_name,
                ContentType="text/csv",
                Body=payload,
            )
            status_code = response.get("ResponseMetadata", {}).get("HTTPStatusCode", 200)
            if status_code != 200:
                failed += 1
                print(f"Warning: invocation for row {idx} returned status {status_code}, skipping.")
                continue

            body = response["Body"].read().decode("utf-8")
            prob = float(body.strip().split(",")[0])
        except Exception as exc:  # noqa: BLE001 -- any invocation failure is a skip, not a crash
            failed += 1
            print(f"Warning: invocation for row {idx} failed ({exc}), skipping.")
            continue

        y_true.append(sample_y.loc[idx])
        y_prob.append(prob)
        y_pred.append(1 if prob >= 0.5 else 0)

    if not y_true:
        raise RuntimeError("All invocations failed. Is the endpoint running?")

    accuracy = accuracy_score(y_true, y_pred)

    try:
        auc = roc_auc_score(y_true, y_prob)
    except ValueError:
        # All predictions/labels are a single class -- AUC is undefined.
        auc = None

    return {
        "accuracy": accuracy,
        "auc": auc,
        "n_samples": len(y_true),
        "endpoint_name": endpoint_name,
    }

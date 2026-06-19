"""Single training script that runs identically locally and on SageMaker.

This script never imports boto3 or sagemaker — it is pure ML code. SageMaker
injects --data-dir=/opt/ml/input/data/train and --model-dir=/opt/ml/model
automatically; locally you pass your own paths.
"""

import argparse
import glob
import os
import sys

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split

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


def load_data(data_dir: str) -> tuple[pd.DataFrame, pd.Series]:
    """Load adult.data (or any .data/.csv file) from data_dir into X, y.

    Raises FileNotFoundError if no .data or .csv file is found in data_dir.
    """
    candidates = sorted(glob.glob(os.path.join(data_dir, "*.data"))) + sorted(
        glob.glob(os.path.join(data_dir, "*.csv"))
    )
    if not candidates:
        found = os.listdir(data_dir) if os.path.isdir(data_dir) else []
        raise FileNotFoundError(
            f"No .data or .csv file found in '{data_dir}'. Found: {found}"
        )
    data_path = candidates[0]

    df = pd.read_csv(data_path, header=None, names=COLUMN_NAMES, skipinitialspace=True)

    string_columns = df.select_dtypes(include="object").columns
    for col in string_columns:
        df[col] = df[col].astype(str).str.strip()

    df = df.replace("?", np.nan)
    df = df.dropna()

    y = df["income"].str.contains(">50K").astype(int)
    X = df.drop(columns=["income"])
    X = pd.get_dummies(X)

    return X, y


def train_model(X_train, y_train, params: dict) -> xgb.XGBClassifier:
    """Fit an XGBClassifier with the given hyperparameters and return it."""
    model = xgb.XGBClassifier(
        use_label_encoder=False,
        eval_metric="logloss",
        **params,
    )
    model.fit(X_train, y_train)
    return model


def evaluate_model(model, X_test, y_test) -> dict:
    """Evaluate model accuracy and print the ACCURACY line SageMaker scrapes for CloudWatch."""
    predictions = model.predict(X_test)
    accuracy = float((predictions == y_test).mean())
    print(f"ACCURACY: {accuracy:.4f}")
    if accuracy < 0.70:
        print(f"WARNING: accuracy {accuracy:.4f} is below the 0.70 threshold")
    return {"accuracy": accuracy, "n_test": int(len(y_test))}


def save_model(model, model_dir: str) -> str:
    """Save model to {model_dir}/model.xgb and return the saved path."""
    os.makedirs(model_dir, exist_ok=True)
    saved_path = os.path.join(model_dir, "model.xgb")
    model.save_model(saved_path)
    return saved_path


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description="Train an XGBoost classifier on the UCI Adult dataset")
    parser.add_argument("--data-dir", default="/opt/ml/input/data/train")
    parser.add_argument("--model-dir", default="/opt/ml/model")
    parser.add_argument("--max-depth", type=int, default=5)
    parser.add_argument("--learning-rate", type=float, default=0.1)
    parser.add_argument("--n-estimators", type=int, default=100)
    args = parser.parse_args(argv)

    X, y = load_data(args.data_dir)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    params = {
        "max_depth": args.max_depth,
        "learning_rate": args.learning_rate,
        "n_estimators": args.n_estimators,
    }
    model = train_model(X_train, y_train, params)
    result = evaluate_model(model, X_test, y_test)
    saved_path = save_model(model, args.model_dir)
    result["model_path"] = saved_path

    return result


if __name__ == "__main__":
    main()
    sys.exit(0)

"""Load the "production"-aliased model from the MLflow Model Registry and
run inference on a few sample rows.
"""
import argparse
import os

import mlflow
import mlflow.pyfunc
import pandas as pd
from dotenv import load_dotenv
from mlflow.exceptions import MlflowException

from train_with_mlflow import COLUMN_NAMES, load_and_split

load_dotenv()


def load_production_model(model_name: str, alias: str) -> mlflow.pyfunc.PyFuncModel:
    """Load the model registered under `model_name` with the given alias."""
    uri = f"models:/{model_name}@{alias}"
    return mlflow.pyfunc.load_model(uri)


def run_inference(model, data_path: str, n_samples: int = 5) -> pd.DataFrame:
    """Run inference on the first n_samples rows of the dataset.

    Preprocesses identically to training (same dummy columns), then predicts.
    Returns a DataFrame with columns ["row", "prediction", "label"].
    """
    # Build training columns the same way load_and_split does, so the dummy
    # encoding for the sample rows lines up with what the model was trained on.
    X_train, _, _, _ = load_and_split(data_path)
    train_columns = X_train.columns

    raw = pd.read_csv(
        data_path,
        names=COLUMN_NAMES,
        sep=r",\s*",
        engine="python",
        na_values="?",
    )
    raw = raw.apply(lambda col: col.str.strip() if col.dtype == "object" else col)
    raw = raw.dropna()

    sample = raw.iloc[:n_samples].reset_index(drop=True)
    labels = sample["income"]

    X_sample = pd.get_dummies(sample.drop(columns=["income"]))
    X_sample = X_sample.reindex(columns=train_columns, fill_value=0)

    predictions = model.predict(X_sample)

    return pd.DataFrame(
        {
            "row": range(n_samples),
            "prediction": predictions,
            "label": labels.values,
        }
    )


def main():
    parser = argparse.ArgumentParser(description="Load production model and run inference")
    parser.add_argument(
        "--model-name",
        type=str,
        default=os.getenv("MLFLOW_MODEL_NAME", "adult-income-xgboost"),
    )
    parser.add_argument("--alias", type=str, default="production")
    parser.add_argument("--data", type=str, default="data/adult.data")
    args = parser.parse_args()

    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))

    try:
        model = load_production_model(args.model_name, args.alias)
    except MlflowException:
        print(f'No model with alias "{args.alias}". Run select_best.py first.')
        return

    results = run_inference(model, args.data, n_samples=5)
    print(results.to_string(index=False))
    print(f'Model loaded from alias "{args.alias}". {len(results)} predictions made.')


if __name__ == "__main__":
    main()

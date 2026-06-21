"""Load the "current" production model from MLflow, train a "challenger"
with different hyperparameters, package both as SageMaker-compatible
model.tar.gz artifacts, and upload them to two distinct S3 prefixes so
deploy_ab.py can stand up a two-variant endpoint.
"""
import argparse
import os
import shutil
import tarfile
import tempfile

import mlflow
import mlflow.xgboost
import pandas as pd
from dotenv import load_dotenv
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

load_dotenv()

COLUMN_NAMES = [
    "age", "workclass", "fnlwgt", "education", "education_num",
    "marital_status", "occupation", "relationship", "race", "sex",
    "capital_gain", "capital_loss", "hours_per_week", "native_country",
    "income",
]

# Path of this module, used to locate inference.py regardless of cwd.
_SRC_DIR = os.path.dirname(os.path.abspath(__file__))


def load_current_model(model_name: str, alias: str) -> XGBClassifier:
    """Load the native XGBClassifier registered under `model_name@alias`.

    This is the "current" production model -- p3-05's best run, served as
    the baseline variant in the A/B test.
    """
    uri = f"models:/{model_name}@{alias}"
    return mlflow.xgboost.load_model(uri)


def _load_and_split(data_path: str):
    """Load the UCI Adult dataset and split into train/test sets.

    Same preprocessing and split (80/20, random_state=42) as p3-01/p3-05/p3-06/p3-07,
    so the challenger's val_AUC is directly comparable to the current model's.
    """
    df = pd.read_csv(
        data_path,
        names=COLUMN_NAMES,
        sep=r",\s*",
        engine="python",
        na_values="?",
    )
    df = df.apply(lambda col: col.str.strip() if col.dtype == "object" else col)
    df = df.dropna()

    y = df["income"].apply(lambda v: 1 if v.strip().rstrip(".") == ">50K" else 0)
    X = df.drop(columns=["income"])
    X = pd.get_dummies(X)

    return train_test_split(X, y, test_size=0.2, random_state=42)


def train_challenger(data_path: str, hyperparams: dict) -> tuple:
    """Train a new XGBClassifier with `hyperparams` and compute its val_AUC
    on a 20% holdout (random_state=42, matching p3-01).

    Returns (challenger_model, challenger_auc).
    """
    X_train, X_test, y_train, y_test = _load_and_split(data_path)

    model = XGBClassifier(eval_metric="logloss", **hyperparams)
    model.fit(X_train, y_train)

    challenger_auc = roc_auc_score(y_test, model.predict_proba(X_test)[:, 1])
    return model, challenger_auc


def package_and_upload(model: XGBClassifier, variant_name: str, bucket: str) -> str:
    """Save `model` to a temp dir as model.xgb, copy in inference.py, package
    both into model.tar.gz, and upload to s3://{bucket}/p3-08/{variant_name}/model.tar.gz.

    Returns the S3 URI.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        model_path = os.path.join(tmp_dir, "model.xgb")
        model.save_model(model_path)

        inference_src = os.path.join(_SRC_DIR, "inference.py")
        inference_dst = os.path.join(tmp_dir, "inference.py")
        shutil.copyfile(inference_src, inference_dst)

        tar_path = os.path.join(tmp_dir, "model.tar.gz")
        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(model_path, arcname="model.xgb")
            tar.add(inference_dst, arcname="inference.py")

        import boto3

        s3 = boto3.client("s3")
        key = f"p3-08/{variant_name}/model.tar.gz"
        s3.upload_file(tar_path, bucket, key)

    return f"s3://{bucket}/{key}"


def main():
    parser = argparse.ArgumentParser(description="Prepare current + challenger model variants for A/B test")
    parser.add_argument("--data", type=str, default="data/adult.data")
    args = parser.parse_args()

    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    model_name = os.getenv("MLFLOW_MODEL_NAME", "adult-income-xgboost")
    bucket = os.environ["S3_BUCKET"]

    hyperparams = {
        "max_depth": int(os.getenv("CHALLENGER_MAX_DEPTH", "7")),
        "learning_rate": float(os.getenv("CHALLENGER_LEARNING_RATE", "0.05")),
        "n_estimators": int(os.getenv("CHALLENGER_N_ESTIMATORS", "200")),
    }

    current_model = load_current_model(model_name, "production")
    challenger_model, challenger_auc = train_challenger(args.data, hyperparams)

    current_uri = package_and_upload(current_model, "current", bucket)
    challenger_uri = package_and_upload(challenger_model, "challenger", bucket)

    assert current_uri != challenger_uri, "current and challenger S3 URIs must be distinct"

    with open(".challenger-auc", "w") as f:
        f.write(str(challenger_auc))

    print(f"Prepared current and challenger variants. Challenger val_AUC: {challenger_auc:.4f}")


if __name__ == "__main__":
    main()

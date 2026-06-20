"""Load the "production"-aliased model from p3-05's MLflow registry, package
it as a SageMaker-compatible model.tar.gz, and upload both the model and the
held-out test set to S3.
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
from mlflow.exceptions import MlflowException
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


def load_model_from_registry(model_name: str, alias: str) -> XGBClassifier:
    """Load the native XGBClassifier registered under `model_name@alias`."""
    uri = f"models:/{model_name}@{alias}"
    try:
        return mlflow.xgboost.load_model(uri)
    except MlflowException as e:
        raise MlflowException(
            f"No model at alias '{alias}'. Run p3-05 select_best.py first."
        ) from e


def create_model_tar(model: XGBClassifier, output_path: str) -> str:
    """Package `model` and inference.py into a SageMaker-compatible tar.gz.

    Both files are added with arcname=basename so they land at the root of
    the archive, not inside a subdirectory -- the XGBoost container looks
    for model.xgb and inference.py directly under the extracted model_dir.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        model_path = os.path.join(tmp_dir, "model.xgb")
        model.save_model(model_path)

        inference_src = os.path.join(_SRC_DIR, "inference.py")
        inference_dst = os.path.join(tmp_dir, "inference.py")
        shutil.copyfile(inference_src, inference_dst)

        os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
        with tarfile.open(output_path, "w:gz") as tar:
            tar.add(model_path, arcname="model.xgb")
            tar.add(inference_dst, arcname="inference.py")

    with tarfile.open(output_path, "r:gz") as tar:
        members = tar.getnames()
        assert "model.xgb" in members, "model.xgb missing from tar.gz root"
        assert "inference.py" in members, "inference.py missing from tar.gz root"

    return output_path


def upload_to_s3(local_path: str, bucket: str, key: str) -> str:
    """Upload `local_path` to s3://{bucket}/{key}. Returns the S3 URI."""
    import boto3

    s3 = boto3.client("s3")
    s3.upload_file(local_path, bucket, key)
    return f"s3://{bucket}/{key}"


def prepare_test_data(data_path: str, output_path: str) -> str:
    """Build the held-out test set (features only) and write it as CSV.

    Preprocessing mirrors p3-05's load_and_split exactly so the dummy-encoded
    columns the model was trained on line up with what gets uploaded here.
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

    from sklearn.model_selection import train_test_split

    X_train, X_test, _, _ = train_test_split(X, y, test_size=0.2, random_state=42)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
    X_test.to_csv(output_path, index=False, header=False)
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Package MLflow model for SageMaker Batch Transform")
    parser.add_argument(
        "--model-name",
        type=str,
        default=os.getenv("MLFLOW_MODEL_NAME", "adult-income-xgboost"),
    )
    parser.add_argument("--alias", type=str, default="production")
    parser.add_argument("--data", type=str, default="data/adult.data")
    args = parser.parse_args()

    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    bucket = os.environ["S3_BUCKET"]

    model = load_model_from_registry(args.model_name, args.alias)

    tar_path = create_model_tar(model, "output/model.tar.gz")
    upload_to_s3(tar_path, bucket, "p3-06/model/model.tar.gz")

    test_csv_path = prepare_test_data(args.data, "data/test.csv")
    upload_to_s3(test_csv_path, bucket, "p3-06/input/test.csv")

    print("Model packaged and uploaded. Test data uploaded. Ready for batch transform.")


if __name__ == "__main__":
    main()

"""Create a SageMaker Model from the packaged artifact, run a Batch Transform
job over the uploaded test set, download the predictions, and score them
against the held-out labels.
"""
import argparse
import os

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sklearn.metrics import accuracy_score

load_dotenv()

COLUMN_NAMES = [
    "age", "workclass", "fnlwgt", "education", "education_num",
    "marital_status", "occupation", "relationship", "race", "sex",
    "capital_gain", "capital_loss", "hours_per_week", "native_country",
    "income",
]


def create_sagemaker_model(model_s3_uri: str, role_arn: str, model_name: str, region: str) -> str:
    """Register a SageMaker Model resource pointing at the XGBoost framework
    container, with our model.tar.gz as the artifact. Returns model_name.
    """
    import boto3
    import sagemaker

    image_uri = sagemaker.image_uris.retrieve("xgboost", region, version="1.7-1")

    client = boto3.client("sagemaker", region_name=region)
    client.create_model(
        ModelName=model_name,
        PrimaryContainer={
            "Image": image_uri,
            "ModelDataUrl": model_s3_uri,
            "Environment": {"SAGEMAKER_PROGRAM": "inference.py"},
        },
        ExecutionRoleArn=role_arn,
    )
    return model_name


def run_transform_job(model_name: str, input_s3: str, output_s3: str, instance_type: str) -> str:
    """Run a Batch Transform job against `model_name`. Blocks until done.

    Raises whatever sagemaker.transformer.Transformer.wait() raises on
    failure; callers should catch and inspect describe_transform_job for the
    failure reason.
    """
    from sagemaker.transformer import Transformer

    transformer = Transformer(
        model_name=model_name,
        instance_count=1,
        instance_type=instance_type,
        output_path=output_s3,
    )
    transformer.transform(input_s3, content_type="text/csv", split_type="Line", wait=True)
    return transformer.latest_transform_job.job_name


def download_and_evaluate(output_s3: str, test_data_path: str, local_output_path: str) -> dict:
    """Download the batch output CSV, score it against the true labels.

    Re-derives y_test with the same 80/20 split (random_state=42) used to
    build the uploaded test.csv, so the labels line up with the predictions.
    """
    import boto3
    from urllib.parse import urlparse

    parsed = urlparse(output_s3)
    bucket = parsed.netloc
    # Batch Transform writes "{input_filename}.out" under the output prefix.
    key = parsed.path.lstrip("/").rstrip("/") + "/test.csv.out"

    os.makedirs(os.path.dirname(os.path.abspath(local_output_path)) or ".", exist_ok=True)
    s3 = boto3.client("s3")
    s3.download_file(bucket, key, local_output_path)

    predictions = pd.read_csv(local_output_path, header=None).iloc[:, 0].to_numpy()

    df = pd.read_csv(
        test_data_path,
        names=COLUMN_NAMES,
        sep=r",\s*",
        engine="python",
        na_values="?",
    )
    df = df.apply(lambda col: col.str.strip() if col.dtype == "object" else col)
    df = df.dropna()

    y = df["income"].apply(lambda v: 1 if v.strip().rstrip(".") == ">50K" else 0)
    X = df.drop(columns=["income"])

    from sklearn.model_selection import train_test_split

    _, _, _, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    y_true = y_test.to_numpy()

    n = min(len(predictions), len(y_true))
    if len(predictions) != len(y_true):
        print(
            f"Warning: prediction count ({len(predictions)}) does not match "
            f"label count ({len(y_true)}). Evaluating on first {n} rows."
        )

    y_pred = (predictions[:n] >= 0.5).astype(int)
    accuracy = accuracy_score(y_true[:n], y_pred)

    return {
        "accuracy": float(accuracy),
        "n_predictions": int(n),
        "output_path": local_output_path,
    }


def main():
    parser = argparse.ArgumentParser(description="Run SageMaker Batch Transform on the packaged model")
    parser.add_argument("--instance-type", type=str, default="ml.m5.large")
    args = parser.parse_args()

    region = os.getenv("AWS_REGION", "us-east-1")
    bucket = os.environ["S3_BUCKET"]
    role_arn = os.environ["SAGEMAKER_ROLE_ARN"]
    model_name = os.getenv("SAGEMAKER_MODEL_NAME", "p3-06-adult-income-batch")

    model_s3_uri = f"s3://{bucket}/p3-06/model/model.tar.gz"
    input_s3 = f"s3://{bucket}/p3-06/input/"
    output_s3 = f"s3://{bucket}/p3-06/output/"

    create_sagemaker_model(model_s3_uri, role_arn, model_name, region)

    try:
        run_transform_job(model_name, input_s3, output_s3, args.instance_type)
    except Exception as e:
        import boto3

        client = boto3.client("sagemaker", region_name=region)
        jobs = client.list_transform_jobs(NameContains=model_name, MaxResults=1)
        if jobs.get("TransformJobSummaries"):
            job_name = jobs["TransformJobSummaries"][0]["TransformJobName"]
            details = client.describe_transform_job(TransformJobName=job_name)
            print(f"Transform job failed: {details.get('FailureReason', str(e))}")
        raise

    result = download_and_evaluate(output_s3, "data/adult.data", "output/predictions.csv")

    print(
        f"Batch transform complete. Accuracy: {result['accuracy']:.4f}. "
        f"Predictions saved to {result['output_path']}."
    )


if __name__ == "__main__":
    main()

"""Compute a SageMaker Model Monitor baseline (statistics.json + constraints.json)
from the UCI Adult training data, using sagemaker.model_monitor.DefaultModelMonitor.suggest_baseline().

The baseline is what every subsequent monitoring run is compared against:
each hourly job runs the same statistics computation over newly-captured
traffic and flags any feature whose distribution has drifted significantly
from this baseline.
"""
import argparse
import os

import boto3
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

COLUMN_NAMES = [
    "age", "workclass", "fnlwgt", "education", "education-num",
    "marital-status", "occupation", "relationship", "race", "sex",
    "capital-gain", "capital-loss", "hours-per-week", "native-country",
    "income",
]


def prepare_baseline_data(data_path: str, output_s3_uri: str) -> str:
    """Load the UCI Adult training data (same preprocessing as p3-01: column
    names, strip, NaN drop, get_dummies), drop the target column, and upload
    the feature-only CSV to S3 for baseline computation.

    Returns the S3 URI of the uploaded file.
    """
    df = pd.read_csv(data_path, header=None, names=COLUMN_NAMES, skipinitialspace=True)

    string_columns = df.select_dtypes(include="object").columns
    for col in string_columns:
        df[col] = df[col].astype(str).str.strip()

    df = df.replace("?", pd.NA)
    df = df.dropna()

    X = df.drop(columns=["income"])
    X = pd.get_dummies(X)

    local_path = "/tmp/p3-10-baseline-data.csv"
    X.to_csv(local_path, index=False, header=True)

    assert output_s3_uri.startswith("s3://"), f"output_s3_uri must be an s3:// URI, got {output_s3_uri}"
    bucket, _, prefix = output_s3_uri[len("s3://"):].partition("/")
    key = f"{prefix.rstrip('/')}/baseline-data.csv" if prefix else "baseline-data.csv"

    s3 = boto3.client("s3")
    s3.upload_file(local_path, bucket, key)

    return f"s3://{bucket}/{key}"


def run_baseline_suggestion(input_s3_uri: str, output_s3_uri: str, role_arn: str, instance_type: str) -> str:
    """Run DefaultModelMonitor.suggest_baseline() on the uploaded training
    CSV and return the S3 URI where statistics.json/constraints.json were
    written.

    Raises a RuntimeError with a clearer message if the job fails because
    the dataset is too small (per the spec's failure-mode table).
    """
    from sagemaker.model_monitor import DatasetFormat, DefaultModelMonitor

    monitor = DefaultModelMonitor(
        role=role_arn,
        instance_count=1,
        instance_type=instance_type,
        volume_size_in_gb=20,
        max_runtime_in_seconds=3600,
    )

    try:
        monitor.suggest_baseline(
            baseline_dataset=input_s3_uri,
            dataset_format=DatasetFormat.csv(header=True),
            output_s3_uri=output_s3_uri,
            wait=True,
        )
    except Exception as exc:
        raise RuntimeError(
            "Baseline suggestion job failed. Ensure training CSV has at least 50 rows. "
            f"Original error: {exc}"
        ) from exc

    return output_s3_uri


def main():
    parser = argparse.ArgumentParser(description="Compute a SageMaker Model Monitor baseline from training data")
    parser.add_argument("--data", type=str, default="data/adult.data")
    parser.add_argument("--instance-type", type=str, default="ml.m5.large")
    args = parser.parse_args()

    role_arn = os.environ["SAGEMAKER_ROLE_ARN"]
    baseline_s3_path = os.environ["S3_BASELINE_PATH"]

    data_s3_uri = baseline_s3_path.rstrip("/") + "/data"

    input_s3_uri = prepare_baseline_data(args.data, data_s3_uri)
    output_s3_uri = run_baseline_suggestion(input_s3_uri, baseline_s3_path, role_arn, args.instance_type)

    print(f"Baseline computed. Statistics at: {output_s3_uri}")

    from sagemaker.model_monitor import DefaultModelMonitor

    monitor = DefaultModelMonitor(role=role_arn)
    monitor.baseline_statistics(output_s3_uri)
    statistics = monitor.baseline_statistics()
    n_features = len(statistics.body_dict.get("features", []))
    print(f"Statistics summary: {n_features} feature(s) monitored")


if __name__ == "__main__":
    main()

"""Load the "production"-aliased model from experiment-tracking's MLflow
registry, package it as a SageMaker-compatible model.tar.gz, upload it to
S3, and stand up a real-time SageMaker endpoint that serves it.
"""
import argparse
import datetime
import os
import shutil
import tarfile
import tempfile

import boto3
import mlflow
import mlflow.xgboost
import sagemaker
from dotenv import load_dotenv

load_dotenv()

# Path of this module, used to locate inference.py regardless of cwd.
_SRC_DIR = os.path.dirname(os.path.abspath(__file__))


def load_and_package_model(
    mlflow_model_name: str, alias: str, s3_bucket: str, s3_prefix: str
) -> str:
    """Load the production model from MLflow, package it with inference.py
    into model.tar.gz, upload to S3, and return the S3 URI.
    """
    uri = f"models:/{mlflow_model_name}@{alias}"
    model = mlflow.xgboost.load_model(uri)

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

        s3 = boto3.client("s3")
        key = f"{s3_prefix}/model.tar.gz"
        s3.upload_file(tar_path, s3_bucket, key)

    return f"s3://{s3_bucket}/{key}"


def create_sagemaker_model(
    model_s3_uri: str, role_arn: str, model_name: str, region: str
) -> None:
    """Register a SageMaker Model resource pointing at the uploaded artifact,
    using the prebuilt XGBoost framework container.
    """
    sm = boto3.client("sagemaker", region_name=region)
    image_uri = sagemaker.image_uris.retrieve("xgboost", region, version="1.7-1")

    sm.create_model(
        ModelName=model_name,
        PrimaryContainer={
            "Image": image_uri,
            "ModelDataUrl": model_s3_uri,
            "Environment": {"SAGEMAKER_PROGRAM": "inference.py"},
        },
        ExecutionRoleArn=role_arn,
    )


def create_endpoint_config(model_name: str, config_name: str, instance_type: str) -> None:
    """Create an endpoint config with a single production variant."""
    sm = boto3.client("sagemaker")
    sm.create_endpoint_config(
        EndpointConfigName=config_name,
        ProductionVariants=[
            {
                "VariantName": "primary",
                "ModelName": model_name,
                "InitialInstanceCount": 1,
                "InstanceType": instance_type,
                "InitialVariantWeight": 1,
            }
        ],
    )


def create_endpoint(config_name: str, endpoint_name: str) -> None:
    """Create the endpoint from `config_name` and block until InService.

    Waiter timeout: 15 minutes (30 checks x 30s), matching SageMaker's
    typical real-time endpoint provisioning time.
    """
    sm = boto3.client("sagemaker")
    sm.create_endpoint(EndpointName=endpoint_name, EndpointConfigName=config_name)

    waiter = sm.get_waiter("endpoint_in_service")
    waiter.wait(
        EndpointName=endpoint_name,
        WaiterConfig={"Delay": 30, "MaxAttempts": 30},
    )


def main():
    parser = argparse.ArgumentParser(description="Deploy production MLflow model to a SageMaker real-time endpoint")
    parser.add_argument(
        "--instance-type",
        type=str,
        default=os.getenv("INFERENCE_INSTANCE_TYPE", "ml.t2.medium"),
    )
    args = parser.parse_args()

    region = os.getenv("AWS_REGION", "us-east-1")
    s3_bucket = os.environ["S3_BUCKET"]
    role_arn = os.environ["SAGEMAKER_ROLE_ARN"]
    mlflow_model_name = os.getenv("MLFLOW_MODEL_NAME", "adult-income-xgboost")
    model_name = os.getenv("SAGEMAKER_MODEL_NAME", "p3-07-adult-income-model")
    config_name = os.getenv("SAGEMAKER_ENDPOINT_CONFIG_NAME", "p3-07-adult-income-config")
    endpoint_name = os.getenv("SAGEMAKER_ENDPOINT_NAME", "p3-07-adult-income-endpoint")

    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))

    model_s3_uri = load_and_package_model(mlflow_model_name, "production", s3_bucket, "p3-07/model")
    create_sagemaker_model(model_s3_uri, role_arn, model_name, region)
    create_endpoint_config(model_name, config_name, args.instance_type)
    create_endpoint(config_name, endpoint_name)

    with open(".endpoint-name", "w") as f:
        f.write(endpoint_name)

    with open(".endpoint-created-at", "w") as f:
        f.write(datetime.datetime.now(datetime.timezone.utc).isoformat())

    print(f"Endpoint {endpoint_name} is InService. Ready for inference.")


if __name__ == "__main__":
    main()

"""Create SageMaker Model resources for both variants, build a two-variant
endpoint config at the configured traffic weights, and stand up the A/B
endpoint.
"""
import argparse
import os

import boto3
import botocore.exceptions
import sagemaker
from dotenv import load_dotenv

load_dotenv()


def create_variant_model(model_s3_uri: str, model_name: str, role_arn: str, region: str) -> None:
    """Register a SageMaker Model resource pointing at the uploaded artifact,
    using the prebuilt XGBoost framework container (same image as p3-07).
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


def create_ab_endpoint_config(
    current_model: str,
    challenger_model: str,
    config_name: str,
    instance_type: str,
    current_weight: int,
    challenger_weight: int,
) -> None:
    """Create an endpoint config with two ProductionVariants ("current" and
    "challenger") at the given traffic weights.

    Validates current_weight + challenger_weight == 10 BEFORE making any AWS
    call -- a misconfigured split should fail fast, not after a partially
    created endpoint config.
    """
    if current_weight + challenger_weight != 10:
        raise ValueError(
            f"Weights must sum to 10, got {current_weight + challenger_weight}"
        )

    sm = boto3.client("sagemaker")
    sm.create_endpoint_config(
        EndpointConfigName=config_name,
        ProductionVariants=[
            {
                "VariantName": "current",
                "ModelName": current_model,
                "InstanceType": instance_type,
                "InitialInstanceCount": 1,
                "InitialVariantWeight": current_weight,
            },
            {
                "VariantName": "challenger",
                "ModelName": challenger_model,
                "InstanceType": instance_type,
                "InitialInstanceCount": 1,
                "InitialVariantWeight": challenger_weight,
            },
        ],
    )


def create_and_wait_endpoint(config_name: str, endpoint_name: str) -> None:
    """Create the endpoint from `config_name` and block until InService.

    Waiter timeout: 15 minutes (30 checks x 30s), matching SageMaker's
    typical real-time endpoint provisioning time. Two production variants
    means two instances to provision, so this can run toward the long end
    of that window.
    """
    sm = boto3.client("sagemaker")
    sm.create_endpoint(EndpointName=endpoint_name, EndpointConfigName=config_name)

    waiter = sm.get_waiter("endpoint_in_service")
    waiter.wait(
        EndpointName=endpoint_name,
        WaiterConfig={"Delay": 30, "MaxAttempts": 30},
    )


def main():
    parser = argparse.ArgumentParser(description="Deploy a two-variant A/B SageMaker endpoint")
    parser.add_argument(
        "--instance-type",
        type=str,
        default=os.getenv("INFERENCE_INSTANCE_TYPE", "ml.t2.medium"),
    )
    args = parser.parse_args()

    region = os.getenv("AWS_REGION", "us-east-1")
    bucket = os.environ["S3_BUCKET"]
    role_arn = os.environ["SAGEMAKER_ROLE_ARN"]

    current_model_name = os.getenv("SAGEMAKER_CURRENT_MODEL_NAME", "p3-08-current-model")
    challenger_model_name = os.getenv("SAGEMAKER_CHALLENGER_MODEL_NAME", "p3-08-challenger-model")
    config_name = os.getenv("SAGEMAKER_ENDPOINT_CONFIG_NAME", "p3-08-ab-config")
    endpoint_name = os.getenv("SAGEMAKER_ENDPOINT_NAME", "p3-08-ab-endpoint")

    current_weight = int(os.getenv("INITIAL_CURRENT_WEIGHT", "9"))
    challenger_weight = int(os.getenv("INITIAL_CHALLENGER_WEIGHT", "1"))

    current_s3_uri = f"s3://{bucket}/p3-08/current/model.tar.gz"
    challenger_s3_uri = f"s3://{bucket}/p3-08/challenger/model.tar.gz"

    try:
        create_variant_model(current_s3_uri, current_model_name, role_arn, region)
        create_variant_model(challenger_s3_uri, challenger_model_name, role_arn, region)

        create_ab_endpoint_config(
            current_model_name,
            challenger_model_name,
            config_name,
            args.instance_type,
            current_weight,
            challenger_weight,
        )

        create_and_wait_endpoint(config_name, endpoint_name)
    except botocore.exceptions.ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "ResourceLimitExceeded":
            print(
                "ResourceLimitExceeded: your account's SageMaker endpoint instance "
                "quota was hit. Request a quota increase at "
                "https://console.aws.amazon.com/servicequotas/home/services/sagemaker/quotas"
            )
        raise

    with open(".endpoint-name", "w") as f:
        f.write(endpoint_name)

    print(
        f"A/B endpoint {endpoint_name} is InService. "
        f"Traffic: {current_weight * 10}% current / {challenger_weight * 10}% challenger"
    )


if __name__ == "__main__":
    main()

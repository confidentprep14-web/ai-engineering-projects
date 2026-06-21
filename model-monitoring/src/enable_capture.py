"""Enable SageMaker Model Monitor data capture on an existing real-time
endpoint by creating a new EndpointConfig (copying the current
ProductionVariants) with DataCaptureConfig turned on, then updating the
endpoint to use it.

SageMaker endpoints are immutable once created -- you cannot flip a flag
on a live endpoint. The only way to change config (including enabling data
capture) is to create a *new* EndpointConfig and call update_endpoint to
swap it in, which triggers a blue/green re-deploy behind the scenes.
"""
import argparse
import os
import time

import boto3
from dotenv import load_dotenv

load_dotenv()


def build_data_capture_config(s3_capture_path: str, capture_percentage: int = 100) -> dict:
    """Build the DataCaptureConfig dict SageMaker expects on an EndpointConfig.

    Pulled out as its own function (rather than inlined in
    enable_data_capture) so its shape can be unit-tested with zero AWS
    calls -- see tests/test_read_violations.py::test_enable_capture_config_has_correct_s3_path.
    """
    return {
        "EnableCapture": True,
        "InitialSamplingPercentage": capture_percentage,
        "DestinationS3Uri": s3_capture_path,
        "CaptureOptions": [
            {"CaptureMode": "Input"},
            {"CaptureMode": "Output"},
        ],
        "CaptureContentTypeHeader": {
            "CsvContentTypes": ["text/csv"],
        },
    }


def enable_data_capture(endpoint_name: str, s3_capture_path: str, capture_percentage: int = 100) -> None:
    """Create a new EndpointConfig with DataCaptureConfig enabled (copying
    the current config's ProductionVariants unchanged) and update the
    endpoint to use it.

    Steps:
    1. Describe current endpoint to get current EndpointConfigName
    2. Describe current config to copy its ProductionVariants
    3. Create a new EndpointConfig with the same variants + DataCaptureConfig
    4. Call update_endpoint
    5. Wait for endpoint to return to InService (waiter, 20-min timeout)
    """
    sm = boto3.client("sagemaker")

    endpoint_desc = sm.describe_endpoint(EndpointName=endpoint_name)
    current_config_name = endpoint_desc["EndpointConfigName"]

    config_desc = sm.describe_endpoint_config(EndpointConfigName=current_config_name)
    production_variants = config_desc["ProductionVariants"]

    new_config_name = f"{current_config_name}-capture-{int(time.time())}"
    data_capture_config = build_data_capture_config(s3_capture_path, capture_percentage)

    sm.create_endpoint_config(
        EndpointConfigName=new_config_name,
        ProductionVariants=production_variants,
        DataCaptureConfig=data_capture_config,
    )

    sm.update_endpoint(EndpointName=endpoint_name, EndpointConfigName=new_config_name)

    # 20-minute timeout: 40 checks x 30s, matching the failure mode in the
    # spec ("Endpoint update takes too long during capture enable").
    waiter = sm.get_waiter("endpoint_in_service")
    waiter.wait(
        EndpointName=endpoint_name,
        WaiterConfig={"Delay": 30, "MaxAttempts": 40},
    )


def verify_capture_enabled(endpoint_name: str) -> bool:
    """Describe the endpoint's current config and return True if
    DataCaptureConfig.EnableCapture is True.
    """
    sm = boto3.client("sagemaker")
    endpoint_desc = sm.describe_endpoint(EndpointName=endpoint_name)
    config_desc = sm.describe_endpoint_config(EndpointConfigName=endpoint_desc["EndpointConfigName"])

    capture_config = config_desc.get("DataCaptureConfig", {})
    return capture_config.get("EnableCapture", False) is True


def main():
    parser = argparse.ArgumentParser(description="Enable SageMaker Model Monitor data capture on an endpoint")
    parser.add_argument("--endpoint-name", type=str, default=os.getenv("ENDPOINT_NAME"))
    parser.add_argument("--capture-percentage", type=int, default=100)
    args = parser.parse_args()

    if not args.endpoint_name:
        raise ValueError("--endpoint-name is required (or set ENDPOINT_NAME in .env)")

    s3_capture_path = os.environ["S3_CAPTURE_PATH"]

    enable_data_capture(args.endpoint_name, s3_capture_path, args.capture_percentage)

    if not verify_capture_enabled(args.endpoint_name):
        raise RuntimeError(
            f"Data capture verification failed for endpoint '{args.endpoint_name}' "
            "-- DataCaptureConfig.EnableCapture is not True after update."
        )

    print(f"Data capture enabled. {args.capture_percentage}% of requests will be logged to {s3_capture_path}")


if __name__ == "__main__":
    main()

"""Measure SageMaker endpoint cold start: delete the existing endpoint,
recreate it, and time from the create_endpoint call to the first successful
prediction.
"""
import argparse
import os
import time

import boto3
from dotenv import load_dotenv

from benchmark import create_sample_payload

load_dotenv()


def delete_endpoint(sm_client, endpoint_name: str) -> None:
    """Delete `endpoint_name` and block until it no longer exists.

    Waiter timeout: 10 minutes (20 checks x 30s).
    """
    sm_client.delete_endpoint(EndpointName=endpoint_name)

    waiter = sm_client.get_waiter("endpoint_deleted")
    waiter.wait(
        EndpointName=endpoint_name,
        WaiterConfig={"Delay": 30, "MaxAttempts": 20},
    )


def time_to_first_prediction(endpoint_name: str, config_name: str, payload: str) -> dict:
    """Recreate the endpoint from `config_name` and measure both time to
    InService and time to the first successful prediction.
    """
    sm_client = boto3.client("sagemaker")
    runtime_client = boto3.client("sagemaker-runtime")

    t_start = time.monotonic()
    sm_client.create_endpoint(EndpointName=endpoint_name, EndpointConfigName=config_name)

    while True:
        status = sm_client.describe_endpoint(EndpointName=endpoint_name)["EndpointStatus"]
        if status == "InService":
            break
        if status == "Failed":
            raise RuntimeError(f"Endpoint {endpoint_name} failed to start")
        time.sleep(10)

    t_inservice = time.monotonic()

    runtime_client.invoke_endpoint(
        EndpointName=endpoint_name,
        ContentType="text/csv",
        Body=payload,
    )
    t_end = time.monotonic()

    return {
        "time_to_inservice_seconds": t_inservice - t_start,
        "time_to_first_prediction_seconds": t_end - t_start,
    }


def main():
    parser = argparse.ArgumentParser(description="Measure SageMaker endpoint cold start time")
    parser.add_argument("--endpoint-name", type=str, required=True)
    parser.add_argument("--data", type=str, default="data/adult.data")
    args = parser.parse_args()

    config_name = os.getenv("SAGEMAKER_ENDPOINT_CONFIG_NAME", "p3-07-adult-income-config")

    sm_client = boto3.client("sagemaker")
    payload = create_sample_payload(args.data, n_rows=1)

    delete_endpoint(sm_client, args.endpoint_name)
    result = time_to_first_prediction(args.endpoint_name, config_name, payload)

    print("Cold start measurement:")
    print(f"  Time to InService: {result['time_to_inservice_seconds']:.1f}s")
    print(f"  Time to first prediction: {result['time_to_first_prediction_seconds']:.1f}s")

    with open(".endpoint-name", "w") as f:
        f.write(args.endpoint_name)


if __name__ == "__main__":
    main()

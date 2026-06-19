"""Fetch the ACCURACY metric from CloudWatch logs for a finished SageMaker
training job.

Requires AWS credentials and a training job that has already produced
CloudWatch log output. Not runnable without a live AWS account.
"""

import argparse
import os
import re
import sys
import time

import boto3
from dotenv import load_dotenv

load_dotenv()

LOG_GROUP = "/aws/sagemaker/TrainingJobs"
ACCURACY_PATTERN = re.compile(r"ACCURACY:\s*(\d+\.\d+)")
POLL_INTERVAL_SECONDS = 10


def fetch_accuracy_from_logs(job_name: str, region: str) -> float | None:
    """Search CloudWatch logs for job_name's ACCURACY line.

    Returns the accuracy as a float, or None if not found (the job may not
    have produced output yet, or its log stream may not exist yet).
    """
    logs_client = boto3.client("logs", region_name=region)

    try:
        streams_response = logs_client.describe_log_streams(
            logGroupName=LOG_GROUP,
            logStreamNamePrefix=job_name,
        )
    except logs_client.exceptions.ResourceNotFoundException:
        return None

    log_streams = streams_response.get("logStreams", [])
    if not log_streams:
        return None

    for stream in log_streams:
        stream_name = stream["logStreamName"]
        paginator = logs_client.get_paginator("filter_log_events")
        for page in paginator.paginate(
            logGroupName=LOG_GROUP,
            logStreamNames=[stream_name],
            filterPattern="ACCURACY",
        ):
            for event in page.get("events", []):
                match = ACCURACY_PATTERN.search(event["message"])
                if match:
                    return float(match.group(1))

    return None


def wait_for_metric(job_name: str, region: str, timeout_seconds: int = 120) -> float:
    """Poll fetch_accuracy_from_logs every 10s until a value is found or timeout.

    Raises TimeoutError if no accuracy is found within timeout_seconds.
    """
    deadline = time.monotonic() + timeout_seconds
    while True:
        accuracy = fetch_accuracy_from_logs(job_name, region)
        if accuracy is not None:
            return accuracy
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"No ACCURACY metric found for job '{job_name}' within "
                f"{timeout_seconds}s in log group {LOG_GROUP}"
            )
        time.sleep(POLL_INTERVAL_SECONDS)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch the accuracy metric from CloudWatch logs for a SageMaker job"
    )
    parser.add_argument("--job-name", required=True)
    parser.add_argument(
        "--region", default=os.environ.get("AWS_REGION", "us-east-1")
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Poll until the metric appears instead of checking once",
    )
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    if args.wait:
        try:
            accuracy = wait_for_metric(args.job_name, args.region, args.timeout)
        except TimeoutError as exc:
            print(f"ERROR: {exc}")
            sys.exit(1)
    else:
        accuracy = fetch_accuracy_from_logs(args.job_name, args.region)
        if accuracy is None:
            print(
                f"No ACCURACY metric found yet for job '{args.job_name}'. "
                "Try again later or pass --wait to poll."
            )
            sys.exit(1)

    print(f"Accuracy: {accuracy}")


if __name__ == "__main__":
    main()

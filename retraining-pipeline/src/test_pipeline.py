"""End-to-end smoke test for the deployed pipeline: upload sample data,
let the S3 event trigger the Lambda, watch the Step Functions execution
run through all 5 states, and report the final status.

This is NOT a pytest test (despite the name, matching the spec's filename)
-- it is a manual CLI script that exercises the real, deployed AWS
infrastructure. It requires state_machine.py --create and
s3_trigger.py --configure to have already run successfully.
"""
import os
import time

import boto3
from dotenv import load_dotenv

import state_machine

load_dotenv()

SAMPLE_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "adult.data")


def main():
    region = os.environ.get("AWS_REGION", "us-east-1")
    bucket = os.environ["S3_BUCKET"]
    prefix = os.environ.get("S3_DATA_PREFIX", "p3-11/incoming/")
    key = f"{prefix.rstrip('/')}/test_run.csv"

    state_machine_arn_file = os.path.join(os.path.dirname(__file__), "..", ".state-machine-arn")
    with open(state_machine_arn_file) as f:
        state_machine_arn = f.read().strip()

    s3_client = boto3.client("s3", region_name=region)
    s3_client.upload_file(SAMPLE_DATA_PATH, bucket, key)

    print("Uploaded test data. Waiting for S3 trigger to start execution...")
    time.sleep(5)

    sfn_client = boto3.client("stepfunctions", region_name=region)

    execution_arn = None
    waited = 5
    while waited <= 60:
        executions = sfn_client.list_executions(
            stateMachineArn=state_machine_arn,
            maxResults=1,
        )
        if executions.get("executions"):
            execution_arn = executions["executions"][0]["executionArn"]
            break
        time.sleep(5)
        waited += 5

    if execution_arn is None:
        print("No execution found. Check S3 notification configuration.")
        return

    result = state_machine.wait_for_execution(execution_arn)
    status = result["status"]

    print(f"Pipeline complete. Status: {status}")


if __name__ == "__main__":
    main()

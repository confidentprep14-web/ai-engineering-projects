"""Check that all four Path 3 components are live before running the
end-to-end test: the SageMaker endpoint (p3-07), the Model Monitor
schedule (p3-10), the Step Functions state machine (p3-11), and the
evaluator Lambda (p3-11).

Pure status-check glue code -- every function here is a thin wrapper
around a single boto3 describe/get call. There is no decision logic to
speak of beyond "did the describe call succeed and is the status the
expected one." See README.md for an honest accounting of how much (or
little) of this project has AWS-free logic worth verifying for real.
"""
import argparse
import os
import sys

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()


def check_endpoint(endpoint_name: str, region: str) -> dict:
    """Describe the SageMaker endpoint. ok=True iff status == InService."""
    client = boto3.client("sagemaker", region_name=region)

    try:
        response = client.describe_endpoint(EndpointName=endpoint_name)
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ValidationException":
            return {"name": endpoint_name, "status": "NOT_FOUND", "ok": False}
        raise

    status = response["EndpointStatus"]
    return {"name": endpoint_name, "status": status, "ok": status == "InService"}


def check_monitoring_schedule(schedule_name: str, region: str) -> dict:
    """Describe the Model Monitor schedule. ok=True iff status == Scheduled."""
    client = boto3.client("sagemaker", region_name=region)

    try:
        response = client.describe_monitoring_schedule(MonitoringScheduleName=schedule_name)
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ValidationException":
            return {"name": schedule_name, "status": "NOT_FOUND", "ok": False}
        raise

    status = response["MonitoringScheduleStatus"]
    return {"name": schedule_name, "status": status, "ok": status == "Scheduled"}


def check_state_machine(arn: str, region: str) -> dict:
    """Describe the Step Functions state machine. ok=True iff status == ACTIVE."""
    client = boto3.client("stepfunctions", region_name=region)

    try:
        response = client.describe_state_machine(stateMachineArn=arn)
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") in ("StateMachineDoesNotExist", "ValidationException"):
            return {"arn": arn, "name": arn, "status": "NOT_FOUND", "ok": False}
        raise

    status = response["status"]
    return {"arn": arn, "name": response["name"], "status": status, "ok": status == "ACTIVE"}


def check_lambda(function_name: str, region: str) -> dict:
    """Get the Lambda function config. ok=True iff the function exists
    (get_function succeeding is itself the liveness signal -- there is no
    separate "status" field analogous to endpoint/schedule states)."""
    client = boto3.client("lambda", region_name=region)

    try:
        response = client.get_function(FunctionName=function_name)
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
            return {"name": function_name, "runtime": "NOT_FOUND", "ok": False}
        raise

    runtime = response["Configuration"]["Runtime"]
    return {"name": function_name, "runtime": runtime, "ok": True}


def verify_all(config: dict) -> dict:
    """Run all four checks and roll them up into one result dict."""
    region = config["region"]

    endpoint = check_endpoint(config["endpoint_name"], region)
    monitoring = check_monitoring_schedule(config["monitoring_schedule_name"], region)
    state_machine = check_state_machine(config["state_machine_arn"], region)
    lambda_fn = check_lambda(config["lambda_evaluator_name"], region)

    all_ok = endpoint["ok"] and monitoring["ok"] and state_machine["ok"] and lambda_fn["ok"]

    return {
        "endpoint": endpoint,
        "monitoring": monitoring,
        "state_machine": state_machine,
        "lambda": lambda_fn,
        "all_ok": all_ok,
    }


def print_component_table(result: dict) -> None:
    """Print the fixed-width component status table. Pure formatting --
    zero AWS dependency, takes only the dict verify_all() returns."""
    endpoint = result["endpoint"]
    monitoring = result["monitoring"]
    state_machine = result["state_machine"]
    lambda_fn = result["lambda"]

    def status_label(ok: bool) -> str:
        return "OK" if ok else "MISSING"

    print("Component Status")
    print("=" * 44)
    print(f"Endpoint:           {endpoint['name']}  [{status_label(endpoint['ok'])}]")
    print(f"Monitoring:         {monitoring['name']}          [{status_label(monitoring['ok'])}]")
    print(f"State Machine:      {state_machine['name']}  [{status_label(state_machine['ok'])}]")
    print(f"Lambda:             {lambda_fn['name']}      [{status_label(lambda_fn['ok'])}]")
    print("-" * 44)
    print(f"Overall:            {'ALL READY' if result['all_ok'] else 'COMPONENTS MISSING'}")


def _load_config() -> dict:
    region = os.environ.get("AWS_REGION", "us-east-1")

    state_machine_arn = os.environ.get("STATE_MACHINE_ARN", "")
    if not state_machine_arn:
        arn_file = os.environ.get("STATE_MACHINE_ARN_FILE", "../retraining-pipeline/.state-machine-arn")
        if os.path.exists(arn_file):
            with open(arn_file) as f:
                state_machine_arn = f.read().strip()

    return {
        "region": region,
        "endpoint_name": os.environ.get("ENDPOINT_NAME", "p3-07-adult-income-endpoint"),
        "monitoring_schedule_name": os.environ.get("MONITORING_SCHEDULE_NAME", "p3-10-hourly-monitor"),
        "state_machine_arn": state_machine_arn,
        "lambda_evaluator_name": os.environ.get("LAMBDA_EVALUATOR_NAME", "p3-11-evaluate-and-deploy"),
    }


def main():
    parser = argparse.ArgumentParser(description="Verify all Path 3 MLOps components are live")
    parser.parse_args()

    config = _load_config()
    result = verify_all(config)
    print_component_table(result)

    if not result["all_ok"]:
        print("Run the setup scripts for any MISSING components.")
        sys.exit(1)
    else:
        print("All components live. Ready to run end_to_end_test.py")
        sys.exit(0)


if __name__ == "__main__":
    main()

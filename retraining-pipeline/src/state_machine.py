"""Create, describe, or delete the p3-11 Step Functions state machine that
wires the 5-state retraining pipeline (preprocess -> train -> evaluate ->
conditional deploy) together.

This is the orchestration layer: the actual SageMaker Processing/Training
jobs run inside AWS-managed infrastructure once the state machine starts an
execution; this file only manages the state machine resource itself and the
helpers for starting/polling an execution.
"""
import argparse
import json
import os
import time

import boto3
from dotenv import load_dotenv

load_dotenv()

DEFINITION_PATH = os.path.join(os.path.dirname(__file__), "state_machine_definition.json")
ARN_FILE = os.path.join(os.path.dirname(__file__), "..", ".state-machine-arn")


def load_definition(path: str) -> str:
    """Read the ASL JSON file, validate it parses, and return the raw JSON
    string (Step Functions' create_state_machine expects a JSON string, not
    a dict)."""
    with open(path) as f:
        content = f.read()

    json.loads(content)  # raises if invalid JSON

    return content


def create_state_machine(name: str, definition: str, role_arn: str, region: str) -> str:
    """Create the Step Functions state machine and return its ARN."""
    client = boto3.client("stepfunctions", region_name=region)

    response = client.create_state_machine(
        name=name,
        definition=definition,
        roleArn=role_arn,
        type="STANDARD",
    )

    return response["stateMachineArn"]


def start_execution(state_machine_arn: str, input_data: dict) -> str:
    """Start an execution of the state machine with the given input and
    return the execution ARN."""
    client = boto3.client("stepfunctions")

    response = client.start_execution(
        stateMachineArn=state_machine_arn,
        input=json.dumps(input_data),
    )

    return response["executionArn"]


def wait_for_execution(execution_arn: str, poll_interval: int = 10) -> dict:
    """Poll describe_execution until the execution reaches a terminal state
    (SUCCEEDED or FAILED), printing each new state transition found in the
    execution's event history as it appears. Returns the final
    describe_execution response dict."""
    client = boto3.client("stepfunctions")

    seen_event_ids = set()

    while True:
        description = client.describe_execution(executionArn=execution_arn)
        status = description["status"]

        history = client.get_execution_history(
            executionArn=execution_arn,
            reverseOrder=False,
        )
        for event in history.get("events", []):
            event_id = event["id"]
            if event_id in seen_event_ids:
                continue
            seen_event_ids.add(event_id)

            event_type = event["type"]
            if event_type.endswith("StateEntered"):
                state_name = event.get("stateEnteredEventDetails", {}).get("name", "?")
                print(f"State entered: {state_name}")
            elif event_type.endswith("StateExited"):
                state_name = event.get("stateExitedEventDetails", {}).get("name", "?")
                print(f"State exited: {state_name}")

        if status in ("SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED"):
            return description

        time.sleep(poll_interval)


def main():
    parser = argparse.ArgumentParser(description="Create/describe/delete the p3-11 Step Functions state machine")
    parser.add_argument("--create", action="store_true")
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--describe", action="store_true")
    parser.add_argument("--delete", action="store_true")
    args = parser.parse_args()

    region = os.environ.get("AWS_REGION", "us-east-1")
    name = os.environ.get("STATE_MACHINE_NAME", "p3-11-ml-pipeline")
    role_arn = os.environ.get("STEP_FUNCTIONS_ROLE_ARN", "")

    client = boto3.client("stepfunctions", region_name=region)

    if args.create:
        definition = load_definition(DEFINITION_PATH)
        try:
            arn = create_state_machine(name, definition, role_arn, region)
        except client.exceptions.StateMachineAlreadyExists:
            print(
                f"State machine '{name}' already exists. Use --update to update its "
                "definition, or --describe to see its current status."
            )
            return

        with open(ARN_FILE, "w") as f:
            f.write(arn)

        print(f"State machine created: {arn}")

    elif args.update:
        if not os.path.exists(ARN_FILE):
            print(f"No {ARN_FILE} found. Run --create first.")
            return
        with open(ARN_FILE) as f:
            arn = f.read().strip()

        definition = load_definition(DEFINITION_PATH)
        client.update_state_machine(stateMachineArn=arn, definition=definition, roleArn=role_arn)
        print(f"State machine updated: {arn}")

    elif args.describe:
        if not os.path.exists(ARN_FILE):
            print(f"No {ARN_FILE} found. Run --create first.")
            return
        with open(ARN_FILE) as f:
            arn = f.read().strip()

        description = client.describe_state_machine(stateMachineArn=arn)
        print(f"Status: {description['status']}")
        print(f"Name: {description['name']}")
        print(f"ARN: {description['stateMachineArn']}")

    elif args.delete:
        if not os.path.exists(ARN_FILE):
            print(f"No {ARN_FILE} found. Nothing to delete.")
            return
        with open(ARN_FILE) as f:
            arn = f.read().strip()

        client.delete_state_machine(stateMachineArn=arn)
        print(f"State machine deleted: {arn}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()

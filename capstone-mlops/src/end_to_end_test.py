"""Orchestrate the full Path 3 MLOps loop in one run: verify components are
live, inject synthetic drift into the endpoint, check the CloudWatch alarm
this should eventually trip, trigger the p3-11 retraining pipeline, watch
the Step Functions execution to completion, and confirm the (possibly newly
deployed) endpoint still returns valid predictions.

This is the capstone's centerpiece script, and it is almost entirely AWS
glue: every one of the five steps either calls boto3 directly or reuses a
boto3-calling helper from an earlier project (model-monitoring's
inject_drift, retraining-pipeline's start_execution/wait_for_execution
pattern). The only non-AWS logic is the [0, 1] probability-range check in
verify_endpoint_predictions and the JSON serialization of the results --
see README.md for the full honest accounting.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime

import boto3
import numpy as np
import pandas as pd
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(__file__))
from verify_components import _load_config, verify_all  # noqa: E402

COLUMN_NAMES = [
    "age", "workclass", "fnlwgt", "education", "education-num",
    "marital-status", "occupation", "relationship", "race", "sex",
    "capital-gain", "capital-loss", "hours-per-week", "native-country",
    "income",
]


def _load_features(data_path: str) -> pd.DataFrame:
    """Load and preprocess the UCI Adult data into the feature frame (no
    target column). Reused verbatim from model-monitoring's
    inject_drift.py -- same training data, same preprocessing."""
    df = pd.read_csv(data_path, header=None, names=COLUMN_NAMES, skipinitialspace=True)

    string_columns = df.select_dtypes(include="object").columns
    for col in string_columns:
        df[col] = df[col].astype(str).str.strip()

    df = df.replace("?", np.nan)
    df = df.dropna()

    return df.drop(columns=["income"])


def inject_drift(endpoint_name: str, data_path: str, n_requests: int = 50) -> dict:
    """Send n_requests inference requests with numeric features shifted to
    mean + 2*std -- reusing p3-10's inject_drift logic so the monitoring
    schedule has abnormal data to flag. Returns {"sent": int, "succeeded": int}."""
    X = _load_features(data_path)
    numeric_cols = X.select_dtypes(include=[np.number]).columns
    categorical_cols = [c for c in X.columns if c not in numeric_cols]

    row = {}
    for col in X.columns:
        if col in numeric_cols:
            row[col] = float(X[col].mean()) + 2.0 * float(X[col].std())
        else:
            row[col] = X[col].mode().iloc[0]

    row_df = pd.DataFrame([row], columns=X.columns)
    X_ohe = pd.get_dummies(X)
    row_ohe = pd.get_dummies(row_df)
    row_ohe = row_ohe.reindex(columns=X_ohe.columns, fill_value=0)
    drifted_row = row_ohe.iloc[0].to_numpy(dtype=float)

    runtime = boto3.client("sagemaker-runtime")
    csv_payload = ",".join(str(v) for v in drifted_row)

    succeeded = 0
    for _ in range(n_requests):
        try:
            runtime.invoke_endpoint(
                EndpointName=endpoint_name,
                ContentType="text/csv",
                Body=csv_payload,
            )
            succeeded += 1
        except Exception:
            pass

    return {"sent": n_requests, "succeeded": succeeded}


def check_alarm_status(endpoint_name: str, region: str) -> list:
    """Describe CloudWatch alarms prefixed with the endpoint name. Does NOT
    wait for the alarm to fire -- only reports current status. Returns a
    list of {"name": str, "state": str} dicts."""
    client = boto3.client("cloudwatch", region_name=region)

    response = client.describe_alarms(AlarmNamePrefix=endpoint_name)
    alarms = [
        {"name": alarm["AlarmName"], "state": alarm["StateValue"]}
        for alarm in response.get("MetricAlarms", [])
    ]

    for alarm in alarms:
        if alarm["state"] == "INSUFFICIENT_DATA":
            print(f"  WARNING: {alarm['name']} is INSUFFICIENT_DATA -- Monitoring may not have run yet")

    return alarms


def trigger_pipeline(state_machine_arn: str, input_data: dict) -> str:
    """Start a Step Functions execution of the retraining pipeline with
    sample input. Returns the execution ARN."""
    client = boto3.client("stepfunctions")

    response = client.start_execution(
        stateMachineArn=state_machine_arn,
        input=json.dumps(input_data),
    )

    return response["executionArn"]


def wait_for_execution(execution_arn: str, timeout_minutes: int = 15) -> dict:
    """Poll the Step Functions execution until it reaches a terminal state
    or timeout_minutes elapses. Prints each new state transition with a
    timestamp, e.g. '[14:32:01] Preprocess -> SUCCEEDED'. Returns the final
    describe_execution response dict; on timeout, returns the last known
    description with status forced to 'TIMED_OUT_LOCALLY' so callers can
    tell a real terminal state apart from a client-side give-up."""
    client = boto3.client("stepfunctions")

    deadline = time.monotonic() + timeout_minutes * 60
    seen_event_ids = set()
    description = None

    while True:
        description = client.describe_execution(executionArn=execution_arn)
        status = description["status"]

        history = client.get_execution_history(executionArn=execution_arn, reverseOrder=False)
        for event in history.get("events", []):
            event_id = event["id"]
            if event_id in seen_event_ids:
                continue
            seen_event_ids.add(event_id)

            event_type = event["type"]
            timestamp = datetime.fromtimestamp(event["timestamp"].timestamp() if hasattr(event["timestamp"], "timestamp") else event["timestamp"]).strftime("%H:%M:%S")

            if event_type.endswith("StateEntered"):
                state_name = event.get("stateEnteredEventDetails", {}).get("name", "?")
                print(f"  [{timestamp}] {state_name} -> RUNNING")
            elif event_type.endswith("StateExited"):
                state_name = event.get("stateExitedEventDetails", {}).get("name", "?")
                print(f"  [{timestamp}] {state_name} -> SUCCEEDED")
            elif event_type == "ExecutionFailed":
                print(f"  [{timestamp}] Execution -> FAILED")

        if status in ("SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED"):
            return description

        if time.monotonic() > deadline:
            print(f"Timed out after {timeout_minutes} minutes. Last known status: {status}")
            description["status"] = "TIMED_OUT_LOCALLY"
            return description

        time.sleep(10)


def verify_endpoint_predictions(endpoint_name: str, data_path: str, n_samples: int = 5) -> dict:
    """Send n_samples inference requests to the endpoint and check that
    every returned prediction is a valid probability in [0, 1]. Returns
    {"predictions": list[float], "all_valid": bool}."""
    X = _load_features(data_path)
    samples = X.head(n_samples)

    X_ohe = pd.get_dummies(X)
    samples_ohe = pd.get_dummies(samples).reindex(columns=X_ohe.columns, fill_value=0)

    runtime = boto3.client("sagemaker-runtime")

    predictions = []
    for _, row in samples_ohe.iterrows():
        csv_payload = ",".join(str(v) for v in row.to_numpy(dtype=float))
        response = runtime.invoke_endpoint(
            EndpointName=endpoint_name,
            ContentType="text/csv",
            Body=csv_payload,
        )
        body = response["Body"].read().decode("utf-8").strip()
        predictions.append(float(body))

    all_valid = all(0.0 <= p <= 1.0 for p in predictions)

    return {"predictions": predictions, "all_valid": all_valid}


def main():
    parser = argparse.ArgumentParser(description="Run the full Path 3 end-to-end MLOps test")
    parser.add_argument("--skip-drift", action="store_true")
    parser.add_argument("--skip-alarm", action="store_true")
    parser.add_argument("--timeout-minutes", type=int, default=15)
    args = parser.parse_args()

    start_time = time.monotonic()
    config = _load_config()
    region = config["region"]
    endpoint_name = config["endpoint_name"]
    data_path = os.environ.get("DRIFT_DATA_PATH", "data/adult.data")

    print("[STEP 1/5] Verifying all components are live...")
    verify_result = verify_all(config)
    if not verify_result["all_ok"]:
        print("Not all components are live. Run verify_components.py for details.")
        sys.exit(1)

    if args.skip_drift:
        print("[STEP 2/5] Skipping drift injection (--skip-drift)...")
        drift_result = {"sent": 0, "succeeded": 0}
    else:
        print("[STEP 2/5] Injecting synthetic drift (50 requests, mean + 2*std)...")
        drift_result = inject_drift(endpoint_name, data_path, n_requests=50)

    if args.skip_alarm:
        print("[STEP 3/5] Skipping alarm check (--skip-alarm)...")
        alarms = []
    else:
        print("[STEP 3/5] Checking CloudWatch alarm status...")
        alarms = check_alarm_status(endpoint_name, region)

    print("[STEP 4/5] Triggering retraining pipeline...")
    execution_arn = trigger_pipeline(config["state_machine_arn"], {"triggered_by": "end_to_end_test"})
    execution_result = wait_for_execution(execution_arn, timeout_minutes=args.timeout_minutes)

    print("[STEP 5/5] Verifying endpoint returns valid predictions...")
    prediction_result = verify_endpoint_predictions(endpoint_name, data_path, n_samples=5)

    elapsed = time.monotonic() - start_time

    pipeline_ok = execution_result["status"] == "SUCCEEDED"
    passed = pipeline_ok and prediction_result["all_valid"]

    results = {
        "verify": verify_result,
        "drift": drift_result,
        "alarms": alarms,
        "execution_arn": execution_arn,
        "execution_status": execution_result["status"],
        "predictions": prediction_result,
        "elapsed_seconds": elapsed,
        "passed": passed,
    }

    os.makedirs("output", exist_ok=True)
    with open("output/e2e_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    if passed:
        print(f"End-to-end test PASSED. Total time: {elapsed:.1f}s")
        sys.exit(0)
    else:
        print(f"End-to-end test FAILED. Total time: {elapsed:.1f}s")
        sys.exit(1)


if __name__ == "__main__":
    main()

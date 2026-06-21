"""Lambda function: compares the just-trained model's AUC against the SSM
baseline and decides whether the pipeline should deploy.

Deployed to AWS Lambda as a zip (see deploy_lambda()). Step Functions invokes
this Lambda's handler() at the "Evaluate" state and reads the returned dict
back as $.evaluation_result.Payload to drive the "ShouldDeploy" Choice state.

Kept dependency-free (only boto3, which ships with the Lambda runtime) so it
never needs a packaged dependency layer -- see the "Lambda zip exceeds size
limit" failure mode in the spec.
"""
import os
import re
import zipfile

import boto3

AUC_LOG_PATTERN = re.compile(r"ACCURACY: (\d+\.\d+)")


def get_training_job_auc(training_job_name: str, region: str) -> float | None:
    """Scan the CloudWatch Logs group for this SageMaker training job and
    return the AUC reported in a line matching 'ACCURACY: (\\d+\\.\\d+)'
    (reusing p3-01's log format). Returns None if no log group, no streams,
    or no matching line is found."""
    logs = boto3.client("logs", region_name=region)
    log_group = f"/aws/sagemaker/TrainingJobs/{training_job_name}"

    try:
        streams_response = logs.describe_log_streams(logGroupName=log_group)
    except logs.exceptions.ResourceNotFoundException:
        return None

    for stream in streams_response.get("logStreams", []):
        stream_name = stream["logStreamName"]
        events_response = logs.get_log_events(
            logGroupName=log_group,
            logStreamName=stream_name,
            startFromHead=True,
        )
        for event in events_response.get("events", []):
            match = AUC_LOG_PATTERN.search(event["message"])
            if match:
                return float(match.group(1))

    return None


def get_baseline_auc(ssm_param_path: str, region: str) -> float | None:
    """Read the baseline AUC from SSM Parameter Store. Returns None if the
    parameter does not exist."""
    ssm = boto3.client("ssm", region_name=region)

    try:
        parameter = ssm.get_parameter(Name=ssm_param_path, WithDecryption=False)
    except ssm.exceptions.ParameterNotFound:
        return None

    return float(parameter["Parameter"]["Value"])


def evaluate_improvement(new_auc: float | None, baseline_auc: float | None, threshold: float = 0.01) -> dict:
    """Pure decision function: should the pipeline deploy the newly trained
    model? Deploys only if new_auc exceeds baseline_auc by strictly more
    than threshold. Has zero AWS dependency -- takes plain floats, returns a
    plain dict."""
    if new_auc is None or baseline_auc is None:
        return {
            "deploy": False,
            "reason": "metrics unavailable",
            "new_auc": None,
            "baseline_auc": None,
        }

    delta = new_auc - baseline_auc
    # Round before comparing: raw float subtraction can land a hair above an
    # exact threshold (e.g. 0.890 - 0.880 == 0.010000000000000009 in IEEE 754
    # double precision), which would wrongly trigger deploy=True for an AUC
    # delta that is exactly at, not above, the threshold. AUC is reported to
    # 4 decimal places throughout this project (see the log regex in
    # get_training_job_auc and the SSM string baseline), so rounding to 4
    # places before the strict-greater-than check preserves real precision
    # while discarding float noise.
    deploy = round(delta, 4) > threshold

    reason = (
        f"AUC improved by {delta:.4f} (threshold {threshold})"
        if deploy
        else f"AUC improved by only {delta:.4f} (threshold {threshold})"
    )

    return {
        "deploy": deploy,
        "reason": reason,
        "new_auc": new_auc,
        "baseline_auc": baseline_auc,
        "delta": delta,
    }


def handler(event: dict, context) -> dict:
    """Lambda entry point. Step Functions invokes this with
    {"training_job_name": ..., "ssm_param_path": ...} and reads the returned
    dict back as the Evaluate state's Payload."""
    region = os.environ.get("AWS_REGION", "us-east-1")

    training_job_name = event["training_job_name"]
    ssm_param_path = event["ssm_param_path"]

    new_auc = get_training_job_auc(training_job_name, region)
    baseline_auc = get_baseline_auc(ssm_param_path, region)

    threshold = float(os.environ.get("AUC_IMPROVEMENT_THRESHOLD", "0.01"))

    return evaluate_improvement(new_auc, baseline_auc, threshold)


def deploy_lambda(function_name: str, role_arn: str, region: str) -> str:
    """Zip this file and create the Lambda function. Returns the Lambda
    ARN."""
    zip_path = "/tmp/lambda_evaluator.zip"
    source_path = os.path.join(os.path.dirname(__file__), "lambda_evaluator.py")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(source_path, arcname="lambda_evaluator.py")

    with open(zip_path, "rb") as f:
        zip_bytes = f.read()

    client = boto3.client("lambda", region_name=region)

    response = client.create_function(
        FunctionName=function_name,
        Runtime="python3.11",
        Role=role_arn,
        Handler="lambda_evaluator.handler",
        Code={"ZipFile": zip_bytes},
        Timeout=30,
        MemorySize=128,
    )

    return response["FunctionArn"]

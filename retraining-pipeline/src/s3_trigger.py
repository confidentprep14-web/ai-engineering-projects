"""Wires an S3 event notification to a trigger Lambda that starts a Step
Functions execution -- this is what makes the pipeline event-driven: a new
file landing under S3_DATA_PREFIX kicks off the whole retraining pipeline
with no manual invocation.

Deploys two Lambdas in total across this project:
  - the evaluator Lambda (lambda_evaluator.py, invoked mid-pipeline by the
    "Evaluate" state)
  - the trigger Lambda (defined inline below, invoked by the S3 event
    notification to start the Step Functions execution)
"""
import argparse
import json
import os
import zipfile

import boto3
from dotenv import load_dotenv

import lambda_evaluator

load_dotenv()

LAMBDA_ARN_FILE = os.path.join(os.path.dirname(__file__), "..", ".lambda-arn")

TRIGGER_LAMBDA_CODE = '''import boto3
import json
import os

def handler(event, context):
    sfn = boto3.client('stepfunctions')
    record = event['Records'][0]['s3']
    bucket = record['bucket']['name']
    key = record['object']['key']

    execution_input = {
        "input_s3_uri": f"s3://{bucket}/{key}",
        "processed_s3_uri": f"s3://{bucket}/p3-11/processed/",
        "model_output_s3_uri": f"s3://{bucket}/p3-11/model-output/",
        "sagemaker_role_arn": os.environ["SAGEMAKER_ROLE_ARN"],
        "lambda_evaluator_arn": os.environ["LAMBDA_EVALUATOR_ARN"],
        "ssm_baseline_param": os.environ["SSM_BASELINE_PARAM"],
        "sns_topic_arn": os.environ["SNS_TOPIC_ARN"],
        "preprocessing_image_uri": os.environ["PREPROCESSING_IMAGE_URI"],
        "training_image_uri": os.environ["TRAINING_IMAGE_URI"],
    }

    sfn.start_execution(
        stateMachineArn=os.environ["STATE_MACHINE_ARN"],
        input=json.dumps(execution_input)
    )
'''


def create_trigger_lambda(function_name: str, state_machine_arn: str, role_arn: str, region: str) -> str:
    """Create the S3-trigger Lambda (separate from the evaluator Lambda)
    whose job is: receive the S3 event, extract the uploaded key, and start
    a Step Functions execution. Returns the Lambda ARN."""
    zip_path = "/tmp/s3_trigger_lambda.zip"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("lambda_function.py", TRIGGER_LAMBDA_CODE)

    with open(zip_path, "rb") as f:
        zip_bytes = f.read()

    client = boto3.client("lambda", region_name=region)

    env_vars = {
        "STATE_MACHINE_ARN": state_machine_arn,
        "SAGEMAKER_ROLE_ARN": os.environ.get("SAGEMAKER_ROLE_ARN", ""),
        "LAMBDA_EVALUATOR_ARN": os.environ.get("LAMBDA_EVALUATOR_ARN", ""),
        "SSM_BASELINE_PARAM": os.environ.get("SSM_BASELINE_PARAM", ""),
        "SNS_TOPIC_ARN": os.environ.get("SNS_TOPIC_ARN", ""),
        "PREPROCESSING_IMAGE_URI": os.environ.get("PREPROCESSING_IMAGE_URI", ""),
        "TRAINING_IMAGE_URI": os.environ.get("TRAINING_IMAGE_URI", ""),
    }

    response = client.create_function(
        FunctionName=function_name,
        Runtime="python3.11",
        Role=role_arn,
        Handler="lambda_function.handler",
        Code={"ZipFile": zip_bytes},
        Timeout=30,
        MemorySize=128,
        Environment={"Variables": env_vars},
    )

    return response["FunctionArn"]


def configure_s3_notification(bucket: str, prefix: str, lambda_arn: str) -> None:
    """Grant S3 permission to invoke the trigger Lambda, then configure the
    bucket's event notification to call it on every ObjectCreated event
    under prefix."""
    region = os.environ.get("AWS_REGION", "us-east-1")

    lambda_client = boto3.client("lambda", region_name=region)
    try:
        lambda_client.add_permission(
            FunctionName=lambda_arn,
            StatementId="AllowS3Invoke",
            Action="lambda:InvokeFunction",
            Principal="s3.amazonaws.com",
            SourceArn=f"arn:aws:s3:::{bucket}",
        )
    except lambda_client.exceptions.ResourceConflictException:
        pass  # permission already granted

    s3_client = boto3.client("s3", region_name=region)
    s3_client.put_bucket_notification_configuration(
        Bucket=bucket,
        NotificationConfiguration={
            "LambdaFunctionConfigurations": [
                {
                    "LambdaFunctionArn": lambda_arn,
                    "Events": ["s3:ObjectCreated:*"],
                    "Filter": {
                        "Key": {
                            "FilterRules": [
                                {"Name": "prefix", "Value": prefix},
                            ]
                        }
                    },
                }
            ]
        },
    )


def main():
    parser = argparse.ArgumentParser(description="Configure the S3 trigger -> Lambda -> Step Functions wiring")
    parser.add_argument("--configure", action="store_true")
    args = parser.parse_args()

    if not args.configure:
        parser.print_help()
        return

    region = os.environ.get("AWS_REGION", "us-east-1")
    bucket = os.environ["S3_BUCKET"]
    prefix = os.environ.get("S3_DATA_PREFIX", "p3-11/incoming/")
    lambda_role_arn = os.environ["LAMBDA_ROLE_ARN"]
    state_machine_arn_file = os.path.join(os.path.dirname(__file__), "..", ".state-machine-arn")

    with open(state_machine_arn_file) as f:
        state_machine_arn = f.read().strip()

    evaluator_function_name = os.environ.get("LAMBDA_FUNCTION_NAME", "p3-11-evaluate-and-deploy")
    evaluator_arn = lambda_evaluator.deploy_lambda(evaluator_function_name, lambda_role_arn, region)
    os.environ["LAMBDA_EVALUATOR_ARN"] = evaluator_arn
    print(f"Evaluator Lambda created: {evaluator_arn}")

    trigger_function_name = f"{evaluator_function_name}-trigger"
    trigger_arn = create_trigger_lambda(trigger_function_name, state_machine_arn, lambda_role_arn, region)
    print(f"Trigger Lambda created: {trigger_arn}")

    ssm_baseline_param = os.environ.get("SSM_BASELINE_PARAM", "/p3-11/baseline/val_auc")
    ssm_client = boto3.client("ssm", region_name=region)
    ssm_client.put_parameter(
        Name=ssm_baseline_param,
        Value="0.883",
        Type="String",
        Overwrite=True,
    )
    print(f"Baseline AUC stored in SSM at {ssm_baseline_param}")

    configure_s3_notification(bucket, prefix, trigger_arn)

    with open(LAMBDA_ARN_FILE, "w") as f:
        f.write(trigger_arn)

    print(f"Pipeline configured. Upload data to s3://{bucket}/{prefix} to trigger.")


if __name__ == "__main__":
    main()

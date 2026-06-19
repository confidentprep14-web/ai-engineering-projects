"""Submit src/main.py as a SageMaker Processing Job using SKLearnProcessor.

Requires AWS credentials and a deployed S3 bucket + SageMaker execution role
(see cdk/ to provision both). Not runnable without a live AWS account.

The same main.py that runs locally runs inside the Processing container —
SKLearnProcessor mounts S3 input at /opt/ml/processing/input/ and collects
/opt/ml/processing/output/ back to S3, then passes --input/--output pointing
at those mounted paths. main.py never needs to know it is in a container.
"""

import argparse
import os
import sys

import boto3
from dotenv import load_dotenv

load_dotenv()

IAM_SETUP_DOC = "https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-roles.html"


def upload_input_data(local_path: str, bucket: str, prefix: str) -> str:
    """Upload raw.csv to s3://{bucket}/{prefix}/raw.csv and return the S3 URI."""
    s3 = boto3.client("s3")
    key = f"{prefix}/raw.csv"
    s3.upload_file(local_path, bucket, key)
    return f"s3://{bucket}/{key}"


def submit_processing_job(input_s3: str, output_s3: str, instance_type: str) -> str:
    """Submit a SageMaker Processing Job that runs src/main.py.

    Returns the processing job name on success. Raises RuntimeError if the
    job fails, printing the FailureReason from describe_processing_job.
    """
    import sagemaker
    from sagemaker.processing import ProcessingInput, ProcessingOutput
    from sagemaker.sklearn.processing import SKLearnProcessor

    role_arn = _require_role_arn()
    region = os.environ.get("AWS_REGION", "us-east-1")
    session = sagemaker.Session(boto3.Session(region_name=region))

    processor = SKLearnProcessor(
        framework_version="1.2-1",
        role=role_arn,
        instance_type=instance_type,
        instance_count=1,
        sagemaker_session=session,
    )

    processor.run(
        code="src/main.py",
        inputs=[
            ProcessingInput(
                source=input_s3,
                destination="/opt/ml/processing/input",
            )
        ],
        outputs=[
            ProcessingOutput(
                source="/opt/ml/processing/output",
                destination=output_s3,
            )
        ],
        arguments=[
            "--input", "/opt/ml/processing/input/raw.csv",
            "--output", "/opt/ml/processing/output/processed.csv",
        ],
        wait=True,
    )

    job_name = processor.latest_job.job_name

    sm_client = boto3.client("sagemaker", region_name=region)
    description = sm_client.describe_processing_job(ProcessingJobName=job_name)
    status = description["ProcessingJobStatus"]
    if status == "Failed":
        reason = description.get("FailureReason", "Unknown failure reason")
        print(f"Processing job {job_name} FAILED: {reason}")
        raise RuntimeError(f"SageMaker processing job {job_name} failed: {reason}")

    return job_name


def download_output(job_name: str, local_dir: str) -> None:
    """Download the processed CSV from the job's S3 output to local_dir."""
    region = os.environ.get("AWS_REGION", "us-east-1")
    sm_client = boto3.client("sagemaker", region_name=region)
    s3 = boto3.client("s3", region_name=region)

    description = sm_client.describe_processing_job(ProcessingJobName=job_name)
    output_s3_uri = description["ProcessingOutputConfig"]["Outputs"][0]["S3Output"]["S3Uri"]

    without_scheme = output_s3_uri[len("s3://"):]
    bucket, _, prefix = without_scheme.partition("/")

    os.makedirs(local_dir, exist_ok=True)
    key = f"{prefix.rstrip('/')}/processed.csv"
    local_path = os.path.join(local_dir, "processed.csv")
    s3.download_file(bucket, key, local_path)

    print(f"Downloaded processed data to {local_dir}")


def _require_role_arn() -> str:
    """Return SAGEMAKER_ROLE_ARN from the environment, or exit with a clear message."""
    role_arn = os.environ.get("SAGEMAKER_ROLE_ARN")
    if not role_arn:
        print(
            "ERROR: SAGEMAKER_ROLE_ARN is not set.\n"
            "Set it in your .env file (copy the role ARN printed by `cdk deploy` "
            f"in cdk/), or create one manually — see {IAM_SETUP_DOC}"
        )
        sys.exit(1)
    return role_arn


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upload data and submit a SageMaker Processing Job running src/main.py"
    )
    parser.add_argument("--instance-type", default="ml.m5.large")
    parser.add_argument(
        "--input-s3", default=None, help="Existing S3 URI for raw.csv (skips upload if set)"
    )
    parser.add_argument(
        "--output-s3", default=None, help="S3 URI prefix to write processed output to"
    )
    parser.add_argument(
        "--data", default="data/raw.csv", help="Local path to raw.csv"
    )
    args = parser.parse_args()

    bucket = os.environ.get("S3_BUCKET")
    if not bucket:
        print(
            "ERROR: S3_BUCKET is not set.\n"
            "Set it in your .env file (copy the bucket name printed by `cdk deploy` in cdk/)."
        )
        sys.exit(1)

    _require_role_arn()

    input_s3 = args.input_s3
    if not input_s3:
        input_s3 = upload_input_data(args.data, bucket, prefix="p3-03/input")
        print(f"Uploaded input data to {input_s3}")

    output_s3 = args.output_s3 or f"s3://{bucket}/p3-03/output"

    job_name = submit_processing_job(input_s3, output_s3, args.instance_type)
    print(f"Processing job {job_name} completed.")

    download_output(job_name, local_dir="data")


if __name__ == "__main__":
    main()

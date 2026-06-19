"""Upload training data to S3, submit a SageMaker training job, wait for it,
and download the resulting model artifact.

Requires AWS credentials and a deployed S3 bucket + SageMaker execution role
(see cdk/ to provision both). Not runnable without a live AWS account.
"""

import argparse
import os
import sys
import tarfile
import tempfile
from pathlib import Path

import boto3
from dotenv import load_dotenv

load_dotenv()

IAM_SETUP_DOC = "https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-roles.html"


def upload_data_to_s3(local_path: str, bucket: str, prefix: str) -> str:
    """Upload adult.data to s3://{bucket}/{prefix}/adult.data and return the S3 URI."""
    s3 = boto3.client("s3")
    key = f"{prefix}/adult.data"
    s3.upload_file(local_path, bucket, key)
    return f"s3://{bucket}/{key}"


def launch_training_job(s3_data_uri: str, instance_type: str, hyperparams: dict) -> str:
    """Submit a SageMaker training job using the built-in XGBoost container.

    Returns the training job name on success. Raises RuntimeError if the job
    fails, printing the FailureReason from describe_training_job.
    """
    import sagemaker
    from sagemaker.estimator import Estimator
    from sagemaker.image_uris import retrieve

    role_arn = _require_role_arn()
    region = os.environ.get("AWS_REGION", "us-east-1")
    session = sagemaker.Session(boto3.Session(region_name=region))

    image_uri = retrieve(framework="xgboost", region=region, version="1.7-1")

    estimator = Estimator(
        image_uri=image_uri,
        role=role_arn,
        instance_count=1,
        instance_type=instance_type,
        entry_point="src/train.py",
        source_dir=".",
        sagemaker_session=session,
        hyperparameters=hyperparams,
    )

    estimator.fit({"train": s3_data_uri}, wait=True)

    job_name = estimator.latest_training_job.name

    sm_client = boto3.client("sagemaker", region_name=region)
    description = sm_client.describe_training_job(TrainingJobName=job_name)
    status = description["TrainingJobStatus"]
    if status == "Failed":
        reason = description.get("FailureReason", "Unknown failure reason")
        print(f"Training job {job_name} FAILED: {reason}")
        raise RuntimeError(f"SageMaker training job {job_name} failed: {reason}")

    return job_name


def download_model_artifact(job_name: str, local_dir: str) -> str:
    """Download model.tar.gz from the job's S3 output, extract model.xgb to local_dir.

    Returns the local path to the extracted model.xgb.
    """
    import sagemaker

    region = os.environ.get("AWS_REGION", "us-east-1")
    session = sagemaker.Session(boto3.Session(region_name=region))
    sm_client = boto3.client("sagemaker", region_name=region)

    description = sm_client.describe_training_job(TrainingJobName=job_name)
    model_artifact_s3_uri = description["ModelArtifacts"]["S3ModelArtifacts"]

    os.makedirs(local_dir, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        # download_data expects a bucket/prefix split, not a full object URI;
        # split off the bucket and key from the s3:// URI.
        without_scheme = model_artifact_s3_uri[len("s3://"):]
        bucket, _, key = without_scheme.partition("/")
        key_prefix = os.path.dirname(key)

        session.download_data(path=tmp_dir, bucket=bucket, key_prefix=key_prefix)

        tarball_path = os.path.join(tmp_dir, os.path.basename(key))
        with tarfile.open(tarball_path, "r:gz") as tar:
            tar.extractall(tmp_dir)

        extracted_model_path = os.path.join(tmp_dir, "model.xgb")
        if not os.path.exists(extracted_model_path):
            raise FileNotFoundError(
                f"model.xgb not found inside {tarball_path} after extraction"
            )

        final_path = os.path.join(local_dir, "model.xgb")
        Path(final_path).write_bytes(Path(extracted_model_path).read_bytes())

    return final_path


def compare_instance_types(s3_data_uri: str, hyperparams: dict) -> None:
    """Launch sequential training jobs on ml.m5.large and ml.m5.xlarge and print cost/time."""
    from cost_estimator import estimate_cost

    region = os.environ.get("AWS_REGION", "us-east-1")
    sm_client = boto3.client("sagemaker", region_name=region)

    for instance_type in ("ml.m5.large", "ml.m5.xlarge"):
        job_name = launch_training_job(s3_data_uri, instance_type, hyperparams)
        description = sm_client.describe_training_job(TrainingJobName=job_name)

        start = description["TrainingStartTime"]
        end = description["TrainingEndTime"]
        minutes = (end - start).total_seconds() / 60
        cost = estimate_cost(instance_type, minutes)

        print(f"{instance_type}: {minutes:.1f} min, ${cost:.4f}")


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
        description="Upload data and submit a SageMaker training job"
    )
    parser.add_argument("--instance-type", default="ml.m5.large")
    parser.add_argument("--max-depth", type=int, default=5)
    parser.add_argument("--learning-rate", type=float, default=0.1)
    parser.add_argument("--n-estimators", type=int, default=100)
    parser.add_argument(
        "--data", default="data/adult.data", help="Local path to adult.data"
    )
    parser.add_argument(
        "--compare-instances",
        action="store_true",
        help="Launch both ml.m5.large and ml.m5.xlarge and compare time/cost",
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

    hyperparams = {
        "max_depth": args.max_depth,
        "learning_rate": args.learning_rate,
        "n_estimators": args.n_estimators,
    }

    s3_data_uri = upload_data_to_s3(args.data, bucket, prefix="p3-01/data")
    print(f"Uploaded training data to {s3_data_uri}")

    if args.compare_instances:
        compare_instance_types(s3_data_uri, hyperparams)
        return

    job_name = launch_training_job(s3_data_uri, args.instance_type, hyperparams)
    print(f"Training job {job_name} completed.")

    model_path = download_model_artifact(job_name, local_dir="models")
    print(f"Model artifact downloaded to {model_path}")


if __name__ == "__main__":
    main()

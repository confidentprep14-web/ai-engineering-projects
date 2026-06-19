# Local to SageMaker

Train an XGBoost model locally, then submit the same script to SageMaker.

## Prerequisites

- Python 3.11+
- AWS credentials configured (`aws configure`) — only needed for the SageMaker step
- An S3 bucket and a SageMaker execution role — provisioned by `cdk deploy` (see below), or create them by hand

## Quick start (local only — no AWS)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
mkdir -p data && curl -o data/adult.data \
  "https://archive.ics.uci.edu/ml/machine-learning-databases/adult/adult.data"
python src/local_train.py --data data/adult.data
```

## Deploy infrastructure

This project needs one S3 bucket (training data + model artifacts) and one IAM role
that SageMaker assumes during training. `cdk/` provisions both with infrastructure
as code instead of clicking through the console.

**Status: unverified — needs AWS credentials.** `cdk synth` was run in this environment
(see GUIDE.md / commit notes) and produces a valid CloudFormation template with no
errors, which confirms the construct code is structurally correct. `cdk deploy` itself
was never run — it requires a real AWS account and was not executed here.

### Permissions you need on your own AWS principal to deploy

To run `cdk bootstrap && cdk deploy` you need an IAM identity (user or role) that can:

- `cloudformation:CreateStack`, `UpdateStack`, `DeleteStack`, `DescribeStacks`, `DescribeStackEvents` — CDK deploys via CloudFormation
- `s3:CreateBucket`, `s3:DeleteBucket`, `s3:PutBucketVersioning`, `s3:PutBucketPolicy` — to create the training bucket
- `iam:CreateRole`, `iam:DeleteRole`, `iam:PutRolePolicy`, `iam:DeleteRolePolicy`, `iam:GetRole` — to create the SageMaker execution role
- `iam:PassRole` — to hand that role to SageMaker when a training job starts
- Standard CDK bootstrap permissions (creates a small CDKToolkit stack + staging bucket the first time you bootstrap an account/region)

This is your **deploy-time** permission set — it is broader than what the SageMaker
role itself gets at runtime (see below), and you would normally hold it as a developer/
admin identity, not bake it into anything that runs unattended.

### What the deployed SageMaker execution role can do at runtime

The role `cdk deploy` creates is deliberately **not** `AmazonSageMakerFullAccess`. It
gets an inline least-privilege policy instead:

- `s3:GetObject`, `s3:PutObject`, `s3:ListBucket` — scoped to the one bucket this stack creates (and its objects), not all S3
- `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents` — scoped to the `/aws/sagemaker/TrainingJobs*` log group prefix
- `sagemaker:CreateTrainingJob`, `sagemaker:DescribeTrainingJob`, `sagemaker:StopTrainingJob` — resource `*` (these specific SageMaker actions do not support resource-level restriction in IAM, so `*` is the correct and documented scope here, not a shortcut)

### Deploy commands

```bash
cd cdk
pip install -r requirements.txt
cdk bootstrap   # first time only, per account/region
cdk deploy
```

`cdk deploy` prints the bucket name and role ARN as stack outputs. Copy both into
your `.env`:

```bash
cp .env.example .env
# Paste BucketName -> S3_BUCKET
# Paste SagemakerRoleArn -> SAGEMAKER_ROLE_ARN
```

## Submit to SageMaker

**Status: unverified — needs AWS credentials.** Code is implemented per spec; never
run end-to-end in this environment.

```bash
python src/sagemaker_launch.py --instance-type ml.m5.large
```

## Compare instance types

```bash
python src/sagemaker_launch.py --compare-instances
```

## Fetch accuracy from CloudWatch

**Status: unverified — needs AWS credentials.**

```bash
python src/metrics_fetcher.py --job-name <job-name>
```

## Estimate cost

```bash
python src/cost_estimator.py --instance ml.m5.large --minutes 5
```

## Tests

```bash
pytest tests/ -v
```

6/6 tests pass locally (4 in `test_train.py`, 2 in `test_cost_estimator.py`) — these
were actually run in this environment and require no AWS account.

## Teardown

**Status: unverified — needs AWS credentials.**

```bash
bash scripts/teardown.sh
```

Deletes: S3 training data, S3 model artifact. Does NOT delete the S3 bucket itself.

## What's verified vs. not

| Piece | Status |
|---|---|
| `src/train.py`, `src/local_train.py`, `src/cost_estimator.py` | Verified — 6/6 pytest passing |
| `cdk/` (`cdk synth`) | Verified — produces a valid CloudFormation template, no AWS account needed |
| `src/sagemaker_launch.py` | Unverified — needs AWS credentials |
| `src/metrics_fetcher.py` | Unverified — needs AWS credentials |
| `scripts/teardown.sh` | Unverified — needs AWS credentials |
| `cdk deploy` (actual infra creation) | Unverified — needs AWS credentials |

# Feature Engineering

Reusable sklearn preprocessing pipeline for UCI Adult Income. Runs locally and as SageMaker Processing.

> Part of [Path 3 — ML Engineering on AWS](https://confidentprep.com/paths/path-3) on Confident Prep — see the full curriculum and how this project fits in.

## Prerequisites

- Python 3.11+
- AWS credentials — only needed for the SageMaker Processing step

## Quick start (local only)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# data/raw.csv is already included (UCI Adult Income, header-less CSV renamed from adult.data)
python src/main.py --input data/raw.csv --output data/processed.csv \
  --save-pipeline pipeline.joblib
```

## What the pipeline does

1. Numeric columns: median imputation -> StandardScaler
2. Categorical columns: most_frequent imputation -> OneHotEncoder (handle_unknown=ignore)
3. ColumnTransformer combines both branches
4. Validates input schema before fitting, validates output (no NaN) after

## Verify no NaN in output

```bash
python -c "import pandas as pd; df=pd.read_csv('data/processed.csv'); print('NaN:', df.isna().sum().sum())"
```

## Deploy infrastructure

This project needs one S3 bucket (Processing Job input + output) and one IAM role
that SageMaker assumes during processing. `cdk/` provisions both with infrastructure
as code instead of clicking through the console.

**Status: unverified — needs AWS credentials.** `cdk synth` was run in this environment
and produces a valid CloudFormation template with no errors, which confirms the
construct code is structurally correct. `cdk deploy` itself was never run — it requires
a real AWS account and was not executed here.

### Permissions you need on your own AWS principal to deploy

To run `cdk bootstrap && cdk deploy` you need an IAM identity (user or role) that can:

- `cloudformation:CreateStack`, `UpdateStack`, `DeleteStack`, `DescribeStacks`, `DescribeStackEvents` — CDK deploys via CloudFormation
- `s3:CreateBucket`, `s3:DeleteBucket`, `s3:PutBucketVersioning`, `s3:PutBucketPolicy` — to create the processing bucket
- `iam:CreateRole`, `iam:DeleteRole`, `iam:PutRolePolicy`, `iam:DeleteRolePolicy`, `iam:GetRole` — to create the SageMaker execution role
- `iam:PassRole` — to hand that role to SageMaker when a Processing Job starts
- Standard CDK bootstrap permissions (creates a small CDKToolkit stack + staging bucket the first time you bootstrap an account/region)

This is your **deploy-time** permission set — it is broader than what the SageMaker
role itself gets at runtime (see below), and you would normally hold it as a developer/
admin identity, not bake it into anything that runs unattended.

### What the deployed SageMaker execution role can do at runtime

The role `cdk deploy` creates is deliberately **not** `AmazonSageMakerFullAccess`. It
gets an inline least-privilege policy instead:

- `s3:GetObject`, `s3:PutObject`, `s3:ListBucket` — scoped to the one bucket this stack creates (and its objects), not all S3
- `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents` — scoped to the `/aws/sagemaker/ProcessingJobs*` log group prefix
- `sagemaker:CreateProcessingJob`, `sagemaker:DescribeProcessingJob`, `sagemaker:StopProcessingJob` — resource `*` (these specific SageMaker actions do not support resource-level restriction in IAM, so `*` is the correct and documented scope here, not a shortcut)

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

## Run as SageMaker Processing Job

**Status: unverified — needs AWS credentials.** Code is implemented per spec; never
run end-to-end in this environment.

```bash
cp .env.example .env  # fill in S3_BUCKET and SAGEMAKER_ROLE_ARN
python src/sagemaker_processor.py
```

## Tests

```bash
pytest tests/ -v
```

6/6 tests pass locally (4 in `test_pipeline.py`, 2 in `test_validator.py`) — these
were actually run in this environment and require no AWS account.

## Teardown

**Status: unverified — needs AWS credentials.**

```bash
bash scripts/teardown.sh
```

Deletes: S3 Processing Job input prefix, S3 Processing Job output prefix. Does NOT
delete the S3 bucket itself.

**If you also deployed the CDK stack:** `cdk destroy` removes the IAM role but does
**not** delete the bucket — it's created with `RemovalPolicy.RETAIN` specifically so a
stack teardown can never silently delete processed data. The bucket will keep costing
(small) S3 storage charges until you empty and delete it yourself:

```bash
aws s3 rm s3://<bucket-name> --recursive
aws s3api delete-bucket --bucket <bucket-name>
```

## What's verified vs. not

| Piece | Status |
|---|---|
| `src/pipeline.py`, `src/validator.py`, `src/main.py` | Verified — 6/6 pytest passing |
| `cdk/` (`cdk synth`) | Verified — produces a valid CloudFormation template, no AWS account needed |
| `src/sagemaker_processor.py` | Unverified — needs AWS credentials |
| `cdk deploy` (actual infra creation) | Unverified — needs AWS credentials |
| `scripts/teardown.sh` | Unverified — needs AWS credentials |

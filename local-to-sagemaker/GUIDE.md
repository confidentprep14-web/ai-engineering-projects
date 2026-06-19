# Guide — Local to SageMaker

## What SageMaker training actually does

When you call `.fit()`:
1. SageMaker pulls a Docker container with XGBoost pre-installed
2. It mounts your S3 data at `/opt/ml/input/data/train/`
3. It runs your `train.py` script inside the container
4. It copies everything your script writes to `/opt/ml/model/` back to S3 as `model.tar.gz`
5. It terminates the instance

Your script does not know it is in SageMaker. That is the point — the same code runs locally and at scale.

## Why the same script works in both places

`train.py` uses `--data-dir` and `--model-dir` arguments. Locally you pass your own paths. SageMaker injects `/opt/ml/input/data/train` and `/opt/ml/model` automatically. The script never imports boto3 or sagemaker — it is pure ML code.

## What to look at in the AWS console

1. **SageMaker → Training jobs** — see the job status, instance type, duration
2. **CloudWatch → Log groups → /aws/sagemaker/TrainingJobs** — see your script's stdout including the `ACCURACY:` line
3. **S3 → your bucket** — see the uploaded data and the output `model.tar.gz`

## Cost breakdown

| Component | Price |
|---|---|
| ml.m5.large per hour | $0.115 |
| ml.m5.xlarge per hour | $0.23 |
| S3 storage (GB/month) | $0.023 |
| S3 PUT request | ~$0.000005 |

A 5-minute training job on ml.m5.large costs about $0.01.

## What to try next

- Change `--n-estimators` to 500. Does it improve accuracy? How much longer does it take?
- Try submitting to ml.m5.xlarge and compare the wall-clock time.
- Open the CloudWatch logs while the job is running — you will see your print statements in near real time.

## Interview framing

"I understand what SageMaker managed training abstracts away — it handles container orchestration, data mounting, and artifact storage — and I know how to write training code that works identically locally and in the cloud by using path arguments instead of hardcoded paths."

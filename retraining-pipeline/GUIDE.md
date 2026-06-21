# Guide — P3-11 Retraining Pipeline

## Why Step Functions

A training pipeline is a sequence of steps that each can fail. Step Functions gives you:
- **Visual execution history:** see exactly which state failed and why
- **Automatic retry:** configure retries per-state without writing retry loops
- **Conditional branching:** the Choice state lets you implement the "only deploy if better"
  rule without coordinating that logic in Python
- **Audit trail:** every execution is logged with full input/output per state

Alternative: Airflow, Prefect, or a Lambda chain. Step Functions integrates natively with
SageMaker via the `sagemaker:createTrainingJob.sync` resource — it polls for completion
automatically. With a Lambda chain you write that polling logic yourself.

## The SSM baseline

SSM Parameter Store stores the baseline AUC as a simple string parameter. When the evaluator
Lambda compares `new_auc > baseline + threshold`, it reads this parameter at runtime.

After a successful deployment, you should update the SSM parameter to the new AUC so the
next pipeline run compares against the most recently deployed model. The `Deploy` state in
this simplified version does not do this — add it as an enhancement.

## S3 event latency

S3 event notifications are usually delivered in seconds, but SLA is "typically less than 1 minute."
In `test_pipeline.py`, a 5-second wait before polling for the execution is usually enough —
but in rare cases the notification may be delayed. If the test times out waiting for an execution,
check the S3 notification configuration and Lambda execution logs.

## The IAM permissions maze

This pipeline requires multiple roles:
- **SageMaker role:** create Processing and Training Jobs, read/write S3
- **Lambda role:** read CloudWatch logs, read SSM, invoke Step Functions
- **Step Functions role:** invoke Lambda, create SageMaker jobs, publish to SNS

Each role needs the right permissions or the state machine will fail at that state. Check
CloudWatch Logs for Lambda errors and Step Functions execution history for SageMaker errors.

## Interview framing

"I built an automated retraining pipeline using Step Functions: S3 upload triggers a Lambda
that starts a 5-state execution — preprocess, train, evaluate, conditional branch, deploy.
The Lambda evaluator compares new AUC to an SSM baseline and only deploys if improvement
exceeds a configurable threshold. The whole thing is event-driven with no polling loop."

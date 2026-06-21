# Operational Runbook — Path 3 MLOps System

## Failure Scenario 1: Endpoint is down

**Symptom:** `verify_components.py` reports `Endpoint: MISSING` or `status: Failed`

**Diagnosis:**
```bash
aws sagemaker describe-endpoint --endpoint-name p3-07-adult-income-endpoint
aws logs get-log-events --log-group-name /aws/sagemaker/Endpoints/p3-07-adult-income-endpoint \
  --log-stream-name $(aws logs describe-log-streams --log-group-name \
  /aws/sagemaker/Endpoints/p3-07-adult-income-endpoint --query 'logStreams[-1].logStreamName' \
  --output text)
```

**Resolution:**
- If status is `Failed`: check logs for container error. Most common: wrong inference.py syntax.
- Re-deploy using p3-07's `deploy.py`. Do not delete prior endpoint config until new one is InService.
- If endpoint was accidentally deleted: re-run `python src/deploy.py` from p3-07.

**Cost impact:** While endpoint is down, no inference cost accrues. Recreating costs a new cold-start.

---

## Failure Scenario 2: Drift alarm fires but retraining pipeline fails

**Symptom:** CloudWatch alarm is in ALARM state but Step Functions execution status is FAILED

**Diagnosis:**
```bash
# Get most recent execution
aws stepfunctions list-executions --state-machine-arn $(cat .state-machine-arn) \
  --status-filter FAILED --query 'executions[0].executionArn' --output text

# Get failure details
aws stepfunctions get-execution-history --execution-arn <arn> \
  --query 'events[?type==`TaskFailed`]'
```

**Common causes and resolutions:**
- **Preprocess state fails:** Check SageMaker Processing Job logs in CloudWatch. Usually: S3 path wrong, container image URI wrong, or IAM role missing S3 permissions.
- **Train state fails:** Check Training Job failure reason: `aws sagemaker describe-training-job --training-job-name <name>`. Usually: data format wrong, out of disk space.
- **Evaluate state fails:** Lambda function error. Check Lambda logs: `aws logs tail /aws/lambda/p3-11-evaluate-and-deploy`.
- **Deploy state fails:** Usually: endpoint already being updated, or IAM role missing SageMaker permissions.

**Resolution:** Fix root cause, then manually start execution:
```bash
python src/test_pipeline.py
```

---

## Failure Scenario 3: Model quality degrades without drift alarm

**Symptom:** p3-09's weekly report shows `Delta: -0.04 (regression — WARNING)` but Model Monitor shows no violations

**Diagnosis:**
This is concept drift — the relationship between features and the label has changed, but the
input feature distributions look the same. Model Monitor cannot detect this.

**Resolution:**
1. Check the weekly report's live accuracy trend over past 4 weeks
2. If accuracy has been declining for 2+ weeks: trigger manual retraining
3. Collect new labeled data if possible — concept drift usually means the world changed
4. Temporarily lower the AUC improvement threshold in SSM to 0.005 to allow easier deployment of retrained models

```bash
aws ssm put-parameter --name /p3-11/baseline/val_auc --value 0.860 --overwrite
python src/test_pipeline.py
```

---

## Failure Scenario 4: AWS costs spike unexpectedly

**Symptom:** `cost_dashboard.py` shows SageMaker cost much higher than expected

**Diagnosis:**
```bash
python src/cost_dashboard.py --days 7
```

Most likely causes:
- Endpoint was not torn down between sessions (p3-07 through p3-10 endpoints accumulate hourly)
- Multiple training jobs running simultaneously (Step Functions executing multiple pipelines)
- Monitoring schedule running more frequently than expected

**Resolution — immediate:**
```bash
bash scripts/teardown_all.sh
```

**Resolution — preventive:**
- Always run teardown scripts at the end of each session
- Set a CloudWatch billing alarm: `aws cloudwatch put-metric-alarm --alarm-name "ML-Cost-Alert" --metric-name EstimatedCharges ...`
- Use `aws ce get-cost-and-usage` daily during active development

**Expected costs when actively using the system:**
- Endpoint idle: ~$0.056/hr (ml.t2.medium)
- Training job: ~$0.01 per run (ml.m5.large, 5 min)
- Monitoring job: ~$0.01 per run
- Step Functions: < $0.01 per execution

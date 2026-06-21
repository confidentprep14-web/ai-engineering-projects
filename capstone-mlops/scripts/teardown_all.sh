#!/usr/bin/env bash
# COMPLETE teardown of every resource created across the entire Path 3
# sequence (p3-07 through p3-12), in strict dependency order: monitoring
# first (so the schedule stops invoking jobs against an endpoint that's
# about to disappear), then the endpoint itself, then the retraining
# pipeline (state machine + Lambdas + S3 trigger + SSM param), then the
# S3 artifacts from each earlier project, oldest-touched last. Run this as
# soon as you're done with the capstone -- with all of p3-07 through p3-11
# live simultaneously, this is the single most expensive project in the
# whole repo to leave running.
#
# Requires AWS credentials and the env vars below (in .env or the
# environment). Not runnable without a live AWS account -- every step is
# `|| true`'d so a missing resource (already torn down, or never created
# in this environment) does not abort the rest of the script.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

if [ -f "$PROJECT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_DIR/.env"
  set +a
fi

AWS_REGION="${AWS_REGION:-us-east-1}"
ENDPOINT_NAME="${ENDPOINT_NAME:-p3-07-adult-income-endpoint}"
ENDPOINT_CONFIG_NAME="${ENDPOINT_CONFIG_NAME:-p3-07-adult-income-config}"
SAGEMAKER_MODEL_NAME="${SAGEMAKER_MODEL_NAME:-p3-07-adult-income-model}"
MONITORING_SCHEDULE_NAME="${MONITORING_SCHEDULE_NAME:-p3-10-hourly-monitor}"
LAMBDA_EVALUATOR_NAME="${LAMBDA_EVALUATOR_NAME:-p3-11-evaluate-and-deploy}"
S3_BUCKET="${S3_BUCKET:-}"
SSM_BASELINE_PARAM="${SSM_BASELINE_PARAM:-/p3-11/baseline/val_auc}"
STATE_MACHINE_ARN_FILE="${STATE_MACHINE_ARN_FILE:-$PROJECT_DIR/../retraining-pipeline/.state-machine-arn}"

echo "=========================================================="
echo "COMPLETE TEARDOWN: all Path 3 resources (p3-07 -> p3-12)"
echo "Region: $AWS_REGION"
echo "=========================================================="

# ---------------------------------------------------------------
# Step 1: Monitoring (p3-10)
# ---------------------------------------------------------------
echo ""
echo "--- Step 1/7: Monitoring (p3-10) ---"
echo "Stopping monitoring schedule: ${MONITORING_SCHEDULE_NAME} ..."
aws sagemaker stop-monitoring-schedule --monitoring-schedule-name "$MONITORING_SCHEDULE_NAME" --region "$AWS_REGION" || true

echo "Deleting monitoring schedule: ${MONITORING_SCHEDULE_NAME} ..."
aws sagemaker delete-monitoring-schedule --monitoring-schedule-name "$MONITORING_SCHEDULE_NAME" --region "$AWS_REGION" || true

if [ -n "$S3_BUCKET" ]; then
  echo "Deleting s3://${S3_BUCKET}/p3-10/ ..."
  aws s3 rm "s3://${S3_BUCKET}/p3-10/" --recursive --region "$AWS_REGION" || true
fi

# ---------------------------------------------------------------
# Step 2: Endpoint (p3-07 and p3-08)
# ---------------------------------------------------------------
echo ""
echo "--- Step 2/7: Endpoint (p3-07, p3-08) ---"
echo "Deleting endpoint: ${ENDPOINT_NAME} ..."
aws sagemaker delete-endpoint --endpoint-name "$ENDPOINT_NAME" --region "$AWS_REGION" || true

echo "Waiting for endpoint deletion to complete..."
aws sagemaker wait endpoint-deleted --endpoint-name "$ENDPOINT_NAME" --region "$AWS_REGION" || true

echo "Deleting endpoint config: ${ENDPOINT_CONFIG_NAME} ..."
aws sagemaker delete-endpoint-config --endpoint-config-name "$ENDPOINT_CONFIG_NAME" --region "$AWS_REGION" || true

echo "Deleting model: ${SAGEMAKER_MODEL_NAME} ..."
aws sagemaker delete-model --model-name "$SAGEMAKER_MODEL_NAME" --region "$AWS_REGION" || true

if [ -n "$S3_BUCKET" ]; then
  echo "Deleting s3://${S3_BUCKET}/p3-07/ ..."
  aws s3 rm "s3://${S3_BUCKET}/p3-07/" --recursive --region "$AWS_REGION" || true
  echo "Deleting s3://${S3_BUCKET}/p3-08/ ..."
  aws s3 rm "s3://${S3_BUCKET}/p3-08/" --recursive --region "$AWS_REGION" || true
fi

# ---------------------------------------------------------------
# Step 3: Retraining pipeline (p3-11)
# ---------------------------------------------------------------
echo ""
echo "--- Step 3/7: Retraining pipeline (p3-11) ---"
if [ -f "$STATE_MACHINE_ARN_FILE" ]; then
  STATE_MACHINE_ARN="$(cat "$STATE_MACHINE_ARN_FILE")"
  echo "Deleting state machine: ${STATE_MACHINE_ARN} ..."
  aws stepfunctions delete-state-machine --state-machine-arn "$STATE_MACHINE_ARN" --region "$AWS_REGION" || true
else
  echo "No state machine ARN file found at ${STATE_MACHINE_ARN_FILE}; skipping state machine deletion."
fi

echo "Deleting evaluator Lambda: ${LAMBDA_EVALUATOR_NAME} ..."
aws lambda delete-function --function-name "$LAMBDA_EVALUATOR_NAME" --region "$AWS_REGION" || true

echo "Deleting S3-trigger Lambda: ${LAMBDA_EVALUATOR_NAME}-trigger (if separate) ..."
aws lambda delete-function --function-name "${LAMBDA_EVALUATOR_NAME}-trigger" --region "$AWS_REGION" || true

if [ -n "$S3_BUCKET" ]; then
  echo "Removing S3 event notification config on bucket: ${S3_BUCKET} ..."
  aws s3api put-bucket-notification-configuration --bucket "$S3_BUCKET" --notification-configuration '{}' --region "$AWS_REGION" || true
fi

echo "Deleting SSM baseline parameter: ${SSM_BASELINE_PARAM} ..."
aws ssm delete-parameter --name "$SSM_BASELINE_PARAM" --region "$AWS_REGION" || true

if [ -n "$S3_BUCKET" ]; then
  echo "Deleting s3://${S3_BUCKET}/p3-11/ ..."
  aws s3 rm "s3://${S3_BUCKET}/p3-11/" --recursive --region "$AWS_REGION" || true
fi

# ---------------------------------------------------------------
# Step 4: Batch artifacts (p3-06)
# ---------------------------------------------------------------
echo ""
echo "--- Step 4/7: Batch artifacts (p3-06) ---"
if [ -n "$S3_BUCKET" ]; then
  echo "Deleting s3://${S3_BUCKET}/p3-06/ ..."
  aws s3 rm "s3://${S3_BUCKET}/p3-06/" --recursive --region "$AWS_REGION" || true
fi

# ---------------------------------------------------------------
# Step 5: Feature engineering (p3-03)
# ---------------------------------------------------------------
echo ""
echo "--- Step 5/7: Feature engineering (p3-03) ---"
if [ -n "$S3_BUCKET" ]; then
  echo "Deleting s3://${S3_BUCKET}/p3-03/ ..."
  aws s3 rm "s3://${S3_BUCKET}/p3-03/" --recursive --region "$AWS_REGION" || true
fi

# ---------------------------------------------------------------
# Step 6: Training artifacts (p3-01)
# ---------------------------------------------------------------
echo ""
echo "--- Step 6/7: Training artifacts (p3-01) ---"
if [ -n "$S3_BUCKET" ]; then
  echo "Deleting s3://${S3_BUCKET}/p3-01/ ..."
  aws s3 rm "s3://${S3_BUCKET}/p3-01/" --recursive --region "$AWS_REGION" || true
fi

if [ -z "$S3_BUCKET" ]; then
  echo "S3_BUCKET not set; all S3 cleanup steps above were skipped."
fi

# ---------------------------------------------------------------
# Step 7: Verify
# ---------------------------------------------------------------
echo ""
echo "--- Step 7/7: Verify ---"
echo "Checking for any remaining p3- endpoints..."
REMAINING_ENDPOINTS=$(aws sagemaker list-endpoints --region "$AWS_REGION" --query 'Endpoints[?contains(EndpointName, `p3-`)]' --output text 2>&1 || true)
if [ -z "$REMAINING_ENDPOINTS" ]; then
  echo "  No p3- endpoints remain."
else
  echo "  WARNING: endpoints may still exist: $REMAINING_ENDPOINTS"
fi

echo "Checking for any remaining p3- state machines..."
REMAINING_STATE_MACHINES=$(aws stepfunctions list-state-machines --region "$AWS_REGION" --query 'stateMachines[?contains(name, `p3-`)]' --output text 2>&1 || true)
if [ -z "$REMAINING_STATE_MACHINES" ]; then
  echo "  No p3- state machines remain."
else
  echo "  WARNING: state machines may still exist: $REMAINING_STATE_MACHINES"
fi

rm -f "$STATE_MACHINE_ARN_FILE"

echo ""
echo "All Path 3 resources deleted."

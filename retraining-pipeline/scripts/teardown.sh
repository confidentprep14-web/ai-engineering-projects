#!/usr/bin/env bash
# Delete every resource this project created, in order: state machine,
# trigger Lambda, evaluator Lambda, the S3 event notification, the SSM
# baseline parameter, any IAM roles created by this project's own scripts,
# and the S3 data under the p3-11/ prefix. Run this as soon as you're done
# testing the pipeline -- the monitoring/training costs are small but the
# state machine, two Lambdas, and S3 notification configuration all keep
# existing (and the S3 notification keeps invoking the trigger Lambda on
# every upload) until explicitly removed.
#
# Requires AWS credentials and STATE_MACHINE_NAME / LAMBDA_FUNCTION_NAME /
# S3_BUCKET / SSM_BASELINE_PARAM set (in .env or the environment). Not
# runnable without a live AWS account.

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
LAMBDA_FUNCTION_NAME="${LAMBDA_FUNCTION_NAME:-p3-11-evaluate-and-deploy}"
LAMBDA_TRIGGER_NAME="${LAMBDA_FUNCTION_NAME}-trigger"
S3_BUCKET="${S3_BUCKET:-}"
SSM_BASELINE_PARAM="${SSM_BASELINE_PARAM:-/p3-11/baseline/val_auc}"

echo "Tearing down p3-11 retraining pipeline resources (region: $AWS_REGION)"

STATE_MACHINE_ARN_FILE="$PROJECT_DIR/.state-machine-arn"
if [ -f "$STATE_MACHINE_ARN_FILE" ]; then
  STATE_MACHINE_ARN="$(cat "$STATE_MACHINE_ARN_FILE")"
  echo "Deleting state machine: ${STATE_MACHINE_ARN} ..."
  aws stepfunctions delete-state-machine --state-machine-arn "$STATE_MACHINE_ARN" --region "$AWS_REGION" || true
else
  echo "No .state-machine-arn file found; skipping state machine deletion."
fi

echo "Deleting trigger Lambda: ${LAMBDA_TRIGGER_NAME} ..."
aws lambda delete-function --function-name "$LAMBDA_TRIGGER_NAME" --region "$AWS_REGION" || true

echo "Deleting evaluator Lambda: ${LAMBDA_FUNCTION_NAME} ..."
aws lambda delete-function --function-name "$LAMBDA_FUNCTION_NAME" --region "$AWS_REGION" || true

if [ -n "$S3_BUCKET" ]; then
  echo "Removing S3 event notification on bucket: ${S3_BUCKET} ..."
  aws s3api put-bucket-notification-configuration --bucket "$S3_BUCKET" --notification-configuration '{}' --region "$AWS_REGION" || true
else
  echo "S3_BUCKET not set; skipping S3 notification removal."
fi

echo "Deleting SSM parameter: ${SSM_BASELINE_PARAM} ..."
aws ssm delete-parameter --name "$SSM_BASELINE_PARAM" --region "$AWS_REGION" || true

echo "Deleting IAM roles created by this project (if any) ..."
for ROLE_NAME in "${SAGEMAKER_ROLE_NAME:-}" "${LAMBDA_ROLE_NAME:-}" "${STEP_FUNCTIONS_ROLE_NAME:-}"; do
  if [ -n "$ROLE_NAME" ]; then
    echo "  Deleting role: ${ROLE_NAME} ..."
    aws iam delete-role --role-name "$ROLE_NAME" || true
  fi
done

if [ -n "$S3_BUCKET" ]; then
  echo "Deleting S3 data under s3://${S3_BUCKET}/p3-11/ ..."
  aws s3 rm "s3://${S3_BUCKET}/p3-11/" --recursive --region "$AWS_REGION" || true
fi

rm -f "$STATE_MACHINE_ARN_FILE" "$PROJECT_DIR/.lambda-arn"

echo "All pipeline resources deleted."

#!/usr/bin/env bash
# Delete the SageMaker Model resource and all S3 objects this project
# created (model artifact, batch input, batch output).
# Does NOT delete the S3 bucket itself — it may be shared with other projects.
#
# Requires AWS credentials and S3_BUCKET / SAGEMAKER_MODEL_NAME set (in .env
# or the environment). Not runnable without a live AWS account.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

if [ -f "$PROJECT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_DIR/.env"
  set +a
fi

if [ -z "${S3_BUCKET:-}" ]; then
  echo "ERROR: S3_BUCKET is not set. Set it in .env or export it before running this script."
  exit 1
fi

AWS_REGION="${AWS_REGION:-us-east-1}"
SAGEMAKER_MODEL_NAME="${SAGEMAKER_MODEL_NAME:-p3-06-adult-income-batch}"
MODEL_PREFIX="p3-06/model/"
INPUT_PREFIX="p3-06/input/"
OUTPUT_PREFIX="p3-06/output/"

echo "Tearing down SageMaker Model and S3 objects in bucket: $S3_BUCKET (region: $AWS_REGION)"

echo "Deleting SageMaker Model: ${SAGEMAKER_MODEL_NAME} ..."
aws sagemaker delete-model --model-name "$SAGEMAKER_MODEL_NAME" --region "$AWS_REGION" || true

echo "Deleting s3://${S3_BUCKET}/${INPUT_PREFIX} ..."
aws s3 rm "s3://${S3_BUCKET}/${INPUT_PREFIX}" --recursive --region "$AWS_REGION" || true

echo "Deleting s3://${S3_BUCKET}/${OUTPUT_PREFIX} ..."
aws s3 rm "s3://${S3_BUCKET}/${OUTPUT_PREFIX}" --recursive --region "$AWS_REGION" || true

echo "Deleting s3://${S3_BUCKET}/${MODEL_PREFIX} ..."
aws s3 rm "s3://${S3_BUCKET}/${MODEL_PREFIX}" --recursive --region "$AWS_REGION" || true

echo "Verifying deletion..."
INPUT_CHECK=$(aws s3 ls "s3://${S3_BUCKET}/${INPUT_PREFIX}" --region "$AWS_REGION" 2>&1 || true)
OUTPUT_CHECK=$(aws s3 ls "s3://${S3_BUCKET}/${OUTPUT_PREFIX}" --region "$AWS_REGION" 2>&1 || true)
MODEL_CHECK=$(aws s3 ls "s3://${S3_BUCKET}/${MODEL_PREFIX}" --region "$AWS_REGION" 2>&1 || true)

if [ -z "$INPUT_CHECK" ] && [ -z "$OUTPUT_CHECK" ] && [ -z "$MODEL_CHECK" ]; then
  echo "No objects found."
else
  echo "WARNING: some objects may still remain:"
  [ -n "$INPUT_CHECK" ] && echo "  input: $INPUT_CHECK"
  [ -n "$OUTPUT_CHECK" ] && echo "  output: $OUTPUT_CHECK"
  [ -n "$MODEL_CHECK" ] && echo "  model: $MODEL_CHECK"
fi

echo "Teardown complete."

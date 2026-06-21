#!/usr/bin/env bash
# Delete the SageMaker endpoint, its endpoint config, and the SageMaker Model
# resource this project created. Run this immediately after you finish
# testing -- the endpoint costs money for every hour it stays InService.
#
# Requires AWS credentials and SAGEMAKER_ENDPOINT_NAME / _CONFIG_NAME /
# _MODEL_NAME / S3_BUCKET set (in .env or the environment). Not runnable
# without a live AWS account.

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
SAGEMAKER_ENDPOINT_NAME="${SAGEMAKER_ENDPOINT_NAME:-p3-07-adult-income-endpoint}"
SAGEMAKER_ENDPOINT_CONFIG_NAME="${SAGEMAKER_ENDPOINT_CONFIG_NAME:-p3-07-adult-income-config}"
SAGEMAKER_MODEL_NAME="${SAGEMAKER_MODEL_NAME:-p3-07-adult-income-model}"

echo "Tearing down endpoint ${SAGEMAKER_ENDPOINT_NAME} and related resources (region: $AWS_REGION)"

echo "Deleting endpoint: ${SAGEMAKER_ENDPOINT_NAME} ..."
aws sagemaker delete-endpoint --endpoint-name "$SAGEMAKER_ENDPOINT_NAME" --region "$AWS_REGION" || true

echo "Waiting for endpoint deletion to complete..."
aws sagemaker wait endpoint-deleted --endpoint-name "$SAGEMAKER_ENDPOINT_NAME" --region "$AWS_REGION" || true

echo "Deleting endpoint config: ${SAGEMAKER_ENDPOINT_CONFIG_NAME} ..."
aws sagemaker delete-endpoint-config --endpoint-config-name "$SAGEMAKER_ENDPOINT_CONFIG_NAME" --region "$AWS_REGION" || true

echo "Deleting model: ${SAGEMAKER_MODEL_NAME} ..."
aws sagemaker delete-model --model-name "$SAGEMAKER_MODEL_NAME" --region "$AWS_REGION" || true

if [ -n "${S3_BUCKET:-}" ]; then
  echo "Deleting s3://${S3_BUCKET}/p3-07/ ..."
  aws s3 rm "s3://${S3_BUCKET}/p3-07/" --recursive --region "$AWS_REGION" || true
fi

echo "Verifying deletion..."
ENDPOINT_CHECK=$(aws sagemaker list-endpoints --name-contains "p3-07" --region "$AWS_REGION" --query 'Endpoints' --output text 2>&1 || true)

if [ -z "$ENDPOINT_CHECK" ]; then
  echo "Endpoint deleted. All resources cleaned up."
else
  echo "WARNING: endpoint may still be listed: $ENDPOINT_CHECK"
fi

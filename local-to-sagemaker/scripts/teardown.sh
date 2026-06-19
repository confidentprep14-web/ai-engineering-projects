#!/usr/bin/env bash
# Delete all S3 objects this project created (training data + model artifact).
# Does NOT delete the S3 bucket itself — it may be shared with other projects.
#
# Requires AWS credentials and S3_BUCKET set (in .env or the environment).
# Not runnable without a live AWS account.

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
DATA_KEY="p3-01/data/adult.data"
OUTPUT_PREFIX="p3-01/output/"

echo "Tearing down S3 objects in bucket: $S3_BUCKET (region: $AWS_REGION)"

echo "Deleting s3://${S3_BUCKET}/${DATA_KEY} ..."
aws s3 rm "s3://${S3_BUCKET}/${DATA_KEY}" --region "$AWS_REGION" || true

echo "Deleting s3://${S3_BUCKET}/${OUTPUT_PREFIX} ..."
aws s3 rm "s3://${S3_BUCKET}/${OUTPUT_PREFIX}" --recursive --region "$AWS_REGION" || true

echo "Verifying deletion..."
DATA_CHECK=$(aws s3 ls "s3://${S3_BUCKET}/${DATA_KEY}" --region "$AWS_REGION" 2>&1 || true)
OUTPUT_CHECK=$(aws s3 ls "s3://${S3_BUCKET}/${OUTPUT_PREFIX}" --region "$AWS_REGION" 2>&1 || true)

if [ -z "$DATA_CHECK" ] && [ -z "$OUTPUT_CHECK" ]; then
  echo "No objects found."
else
  echo "WARNING: some objects may still remain:"
  [ -n "$DATA_CHECK" ] && echo "  data: $DATA_CHECK"
  [ -n "$OUTPUT_CHECK" ] && echo "  output: $OUTPUT_CHECK"
fi

echo "Teardown complete. Estimated charges: < \$0.50"

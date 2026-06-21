#!/usr/bin/env bash
# Stop and delete the SageMaker Model Monitor schedule, then delete the S3
# capture, baseline, and monitoring-results data this project created. Run
# this as soon as you're done reading violation reports -- the monitoring
# schedule keeps billing a small job every hour until it's deleted, and the
# endpoint itself is shut down by p3-07's own teardown, not this script.
#
# Requires AWS credentials and MONITORING_SCHEDULE_NAME / S3_CAPTURE_PATH /
# S3_BASELINE_PATH / S3_MONITORING_RESULTS_PATH set (in .env or the
# environment). Not runnable without a live AWS account.

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
MONITORING_SCHEDULE_NAME="${MONITORING_SCHEDULE_NAME:-p3-10-hourly-monitor}"
S3_CAPTURE_PATH="${S3_CAPTURE_PATH:-}"
S3_BASELINE_PATH="${S3_BASELINE_PATH:-}"
S3_MONITORING_RESULTS_PATH="${S3_MONITORING_RESULTS_PATH:-}"

echo "Tearing down Model Monitor schedule ${MONITORING_SCHEDULE_NAME} and related resources (region: $AWS_REGION)"

echo "Stopping monitoring schedule: ${MONITORING_SCHEDULE_NAME} ..."
aws sagemaker stop-monitoring-schedule --monitoring-schedule-name "$MONITORING_SCHEDULE_NAME" --region "$AWS_REGION" || true

echo "Deleting monitoring schedule: ${MONITORING_SCHEDULE_NAME} ..."
aws sagemaker delete-monitoring-schedule --monitoring-schedule-name "$MONITORING_SCHEDULE_NAME" --region "$AWS_REGION" || true

if [ -n "$S3_CAPTURE_PATH" ]; then
  echo "Deleting S3 capture data: ${S3_CAPTURE_PATH} ..."
  aws s3 rm "$S3_CAPTURE_PATH" --recursive --region "$AWS_REGION" || true
fi

if [ -n "$S3_BASELINE_PATH" ]; then
  echo "Deleting S3 baseline data: ${S3_BASELINE_PATH} ..."
  aws s3 rm "$S3_BASELINE_PATH" --recursive --region "$AWS_REGION" || true
fi

if [ -n "$S3_MONITORING_RESULTS_PATH" ]; then
  echo "Deleting S3 monitoring results: ${S3_MONITORING_RESULTS_PATH} ..."
  aws s3 rm "$S3_MONITORING_RESULTS_PATH" --recursive --region "$AWS_REGION" || true
fi

echo "Monitoring resources deleted."
echo "Note: the endpoint itself is managed by p3-07's teardown, not this script."

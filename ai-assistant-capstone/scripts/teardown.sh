#!/bin/bash
set -e
source .env
source .deployed.env 2>/dev/null || { echo "Run deploy.sh first"; exit 1; }

echo "=== Tearing down all resources ==="

aws apigatewayv2 delete-api --api-id "${API_ID}" && echo "✓ API Gateway deleted"
aws lambda delete-function --function-name "${LAMBDA_FUNCTION_NAME}" && echo "✓ Lambda deleted"
aws iam delete-role-policy --role-name "${LAMBDA_FUNCTION_NAME}-role" --policy-name "least-privilege"
aws iam delete-role --role-name "${LAMBDA_FUNCTION_NAME}-role" && echo "✓ IAM role deleted"
aws ecr delete-repository --repository-name "${ECR_REPO_NAME}" --force && echo "✓ ECR repo deleted"
aws secretsmanager delete-secret --secret-id "${SECRET_NAME}" --force-delete-without-recovery && echo "✓ Secret deleted"
aws cloudwatch delete-alarms --alarm-names "${LAMBDA_FUNCTION_NAME}-error-rate" && echo "✓ Alarm deleted"
aws logs delete-log-group --log-group-name "/aws/lambda/${LAMBDA_FUNCTION_NAME}" && echo "✓ Log group deleted"
rm -f .deployed.env

echo "=== All resources deleted ==="
echo "Verify: aws lambda list-functions --query 'Functions[?FunctionName==\`${LAMBDA_FUNCTION_NAME}\`]'"

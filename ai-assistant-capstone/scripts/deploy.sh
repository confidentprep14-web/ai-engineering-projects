#!/bin/bash
set -e
source .env

echo "=== Deploying Full AI Assistant Capstone to Lambda ==="

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}"

# 1. Create ECR repo (skip if exists)
echo "[1/7] Creating ECR repository..."
aws ecr create-repository --repository-name "${ECR_REPO_NAME}" \
    --region "${AWS_REGION}" 2>/dev/null || echo "ECR repo already exists"

# 2. Build and push image
echo "[2/7] Building Docker image..."
docker build -t "${ECR_REPO_NAME}" .
aws ecr get-login-password --region "${AWS_REGION}" | \
    docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
docker tag "${ECR_REPO_NAME}:latest" "${ECR_URI}:latest"
docker push "${ECR_URI}:latest"
echo "Pushed: ${ECR_URI}:latest"

# 3. Store secret in Secrets Manager
echo "[3/7] Storing API key in Secrets Manager..."
aws secretsmanager create-secret \
    --name "${SECRET_NAME}" \
    --secret-string "{\"LLM_API_KEY\": \"${LLM_API_KEY}\"}" \
    --region "${AWS_REGION}" 2>/dev/null || \
aws secretsmanager update-secret \
    --secret-id "${SECRET_NAME}" \
    --secret-string "{\"LLM_API_KEY\": \"${LLM_API_KEY}\"}" \
    --region "${AWS_REGION}"

# 4. Create IAM role
echo "[4/7] Creating IAM execution role..."
TRUST_POLICY='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
ROLE_ARN=$(aws iam create-role \
    --role-name "${LAMBDA_FUNCTION_NAME}-role" \
    --assume-role-policy-document "${TRUST_POLICY}" \
    --query 'Role.Arn' --output text 2>/dev/null || \
    aws iam get-role --role-name "${LAMBDA_FUNCTION_NAME}-role" --query 'Role.Arn' --output text)
aws iam put-role-policy \
    --role-name "${LAMBDA_FUNCTION_NAME}-role" \
    --policy-name "least-privilege" \
    --policy-document file://infra/iam_policy.json
sleep 10  # IAM propagation delay

# 5. Create or update Lambda function
echo "[5/7] Deploying Lambda function..."
aws lambda create-function \
    --function-name "${LAMBDA_FUNCTION_NAME}" \
    --package-type Image \
    --code ImageUri="${ECR_URI}:latest" \
    --role "${ROLE_ARN}" \
    --memory-size "${LAMBDA_MEMORY_MB}" \
    --timeout "${LAMBDA_TIMEOUT_SECONDS}" \
    --environment "Variables={LLM_PROVIDER=${LLM_PROVIDER},LLM_MODEL=${LLM_MODEL},SECRET_NAME=${SECRET_NAME},AWS_REGION=${AWS_REGION}}" \
    --region "${AWS_REGION}" 2>/dev/null || \
aws lambda update-function-code \
    --function-name "${LAMBDA_FUNCTION_NAME}" \
    --image-uri "${ECR_URI}:latest" \
    --region "${AWS_REGION}"
aws lambda wait function-updated --function-name "${LAMBDA_FUNCTION_NAME}"

# 6. Create CloudWatch log group and alarm
echo "[6/7] Setting up CloudWatch alarm..."
aws logs create-log-group --log-group-name "/aws/lambda/${LAMBDA_FUNCTION_NAME}" 2>/dev/null || true
aws logs put-retention-policy --log-group-name "/aws/lambda/${LAMBDA_FUNCTION_NAME}" --retention-in-days 7
aws cloudwatch put-metric-alarm \
    --alarm-name "${LAMBDA_FUNCTION_NAME}-error-rate" \
    --alarm-description "Alert if error rate exceeds 5% in 5 minutes" \
    --metric-name Errors --namespace AWS/Lambda \
    --dimensions Name=FunctionName,Value="${LAMBDA_FUNCTION_NAME}" \
    --statistic Sum --period 300 --threshold 5 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 1 \
    --alarm-actions "${SNS_ALARM_TOPIC_ARN}"

# 7. Create API Gateway HTTP API
echo "[7/7] Creating API Gateway..."
API_ID=$(aws apigatewayv2 create-api \
    --name "${LAMBDA_FUNCTION_NAME}-api" \
    --protocol-type HTTP \
    --query 'ApiId' --output text)
INTEGRATION_ID=$(aws apigatewayv2 create-integration \
    --api-id "${API_ID}" \
    --integration-type AWS_PROXY \
    --integration-uri "arn:aws:lambda:${AWS_REGION}:${ACCOUNT_ID}:function:${LAMBDA_FUNCTION_NAME}" \
    --payload-format-version "2.0" \
    --query 'IntegrationId' --output text)
aws apigatewayv2 create-route \
    --api-id "${API_ID}" \
    --route-key "ANY /{proxy+}" \
    --target "integrations/${INTEGRATION_ID}"
aws apigatewayv2 create-stage \
    --api-id "${API_ID}" --stage-name "\$default" --auto-deploy
aws lambda add-permission \
    --function-name "${LAMBDA_FUNCTION_NAME}" \
    --statement-id "apigw-invoke" \
    --action "lambda:InvokeFunction" \
    --principal "apigateway.amazonaws.com" \
    --source-arn "arn:aws:execute-api:${AWS_REGION}:${ACCOUNT_ID}:${API_ID}/*"

API_URL="https://${API_ID}.execute-api.${AWS_REGION}.amazonaws.com"
echo ""
echo "=== Deployment complete ==="
echo "API URL: ${API_URL}"
echo "Test: curl ${API_URL}/health"
echo ""
echo "⚠  REMEMBER: Run 'bash scripts/teardown.sh' when done to avoid charges"
# Save API_URL for other scripts
echo "API_URL=${API_URL}" >> .deployed.env
echo "API_ID=${API_ID}" >> .deployed.env
echo "ACCOUNT_ID=${ACCOUNT_ID}" >> .deployed.env

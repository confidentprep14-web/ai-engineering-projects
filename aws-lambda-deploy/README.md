# Deploy to AWS Lambda

Packages the streaming chat API as a Lambda-compatible container image, deploys it
with a least-privilege IAM role and API Gateway, stores secrets in Secrets Manager,
and measures cold start latency.

## Deployment status

**Status: unverified — needs AWS credentials.** This project was built and tested in
an environment with no AWS account configured (`aws sts get-caller-identity` fails
here). What *was* verified without any AWS account:

- `docker build -t chat-api-lambda .` — runs successfully end-to-end. Pulls
  `public.ecr.aws/lambda/python:3.12`, installs `requirements.txt`, copies `src/`,
  and produces a tagged image (`chat-api-lambda:latest`). This confirms the
  Dockerfile and dependency set are correct for the Lambda container runtime.
- All unit tests in `tests/` — 15/15 passing locally, no AWS or LLM provider calls
  in the main path (see Tests section below).
- Every file in `src/` is under 200 lines.

`scripts/deploy.sh`, `scripts/teardown.sh`, `scripts/test.sh`, and
`scripts/measure_cold_start.py` are implemented exactly per spec but were never run
against a real AWS account — they require IAM permissions, ECR, Lambda, API Gateway,
Secrets Manager, and CloudWatch access that does not exist in this build environment.
If you have an AWS account, follow Setup → Deploy → Test → Teardown below; the
scripts are ready to run as-is.

| Component | Status |
|---|---|
| `src/` (FastAPI app, config, database, rate limiter, llm) | Verified — 15/15 pytest passing locally |
| `Dockerfile` / `docker build` | Verified — builds successfully against the real Lambda base image |
| `scripts/deploy.sh` | Unverified — needs AWS credentials |
| `scripts/test.sh` | Unverified — needs AWS credentials |
| `scripts/measure_cold_start.py` | Unverified — needs AWS credentials |
| `scripts/teardown.sh` | Unverified — needs AWS credentials |

## Prerequisites

- AWS account with CLI configured (`aws sts get-caller-identity` works)
- Docker Desktop running
- LLM API key (Anthropic or OpenAI)
- SNS topic for alarm notifications (create in AWS console first)

## Setup

```bash
cd aws-lambda-deploy
cp .env.example .env
# Edit .env: set AWS_REGION, LLM_API_KEY, SNS_ALARM_TOPIC_ARN
```

## Deploy

```bash
bash scripts/deploy.sh
```

This creates: ECR repo → builds+pushes image → Secrets Manager secret → IAM role →
Lambda function → CloudWatch alarm → API Gateway HTTP API.

## Test

```bash
source .deployed.env
curl https://${API_ID}.execute-api.${AWS_REGION}.amazonaws.com/health
python scripts/measure_cold_start.py
```

## TEARDOWN (run when done)

```bash
bash scripts/teardown.sh
```

Deletes everything. Verify with `aws lambda list-functions`.

## Tests

```bash
pip install -r requirements.txt pytest
pytest tests/ -v
```

15/15 tests pass locally — covers the rate limiter's sliding window, the
`/tmp`-based database default, the FastAPI routes (health, rate limiting, stats,
unknown-provider error), and `config.get_llm_api_key()`'s fallback from Secrets
Manager to a plain environment variable. The Secrets Manager branch is exercised
with a mocked `boto3.client` (an AWS infra call, not an LLM provider call) so the
wiring is verified without ever touching a real AWS account.

## What to try next

- Check the Lambda function's memory usage in CloudWatch — try reducing from 512MB
- Enable provisioned concurrency and compare cold start latency
- Add the prompt evaluation from p1-09 as a Lambda function

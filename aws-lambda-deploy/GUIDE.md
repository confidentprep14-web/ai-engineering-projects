# Build guide: Deploy to AWS Lambda

## What you're building and why it matters

Lambda is the most common way to deploy LLM inference endpoints at small-to-medium
scale. You pay per invocation, not per hour — if your app gets 100 requests/day,
you pay for 100 invocations, not for 24 hours of a running server. Container images
on Lambda (as opposed to zip file deployments) support dependencies like FastAPI and
anthropic that are too large for the 250MB zip limit. Understanding IAM, cold starts,
and Secrets Manager is not optional for production AI work — these are the primitives
every cloud-deployed LLM application depends on.

## The decision that matters in this build

**Least-privilege IAM.** The execution role in this project has exactly two permissions:
write CloudWatch logs, and read from one Secrets Manager path. That's it. No
AdministratorAccess, no `*` on resources. A compromised Lambda function with
AdministratorAccess is a full account takeover. A compromised function with
least-privilege can read one API key and write logs. Least-privilege is not a
compliance checkbox — it is the blast radius control for when things go wrong.

## What will break

**IAM propagation takes 10–15 seconds.** After creating the role, Lambda needs time
to see it. The deploy script has `sleep 10` for this reason. If you remove it,
Lambda may fail with "role not found" on creation.

**Cold starts are real on container images.** Your first invocation after a period
of inactivity will take 3–8 seconds. This is the container cold start. The
`measure_cold_start.py` script shows you the full distribution. Provisioned
concurrency eliminates it but costs money continuously.

## How to talk about this in an interview

"I deployed a containerised FastAPI app to Lambda with a least-privilege execution
role — the role can only write logs and read one secret. I stored the LLM API key
in Secrets Manager, not as a plaintext Lambda environment variable. I measured cold
start at p95 = 5.2 seconds on a 512MB function — acceptable for my use case but
I know exactly how to eliminate it with provisioned concurrency if latency SLA required."

## Cost estimate

| Resource | Pricing dimension | Expected usage | Estimated cost |
|----------|------------------|---------------|----------------|
| Lambda | $0.0000166667/GB-second | 512MB × 30s × 50 invocations | ~$0.01 |
| API Gateway HTTP API | $1/million requests | 50 requests | <$0.01 |
| ECR | $0.10/GB-month | ~1GB image, <1 hour | ~$0.001 |
| Secrets Manager | $0.40/secret/month | 1 secret, <1 hour | <$0.001 |
| CloudWatch | Free tier (first 10 alarms) | 1 alarm | $0 |
| **Total** | | | **~$1–3** |

## Teardown checklist

Run `bash scripts/teardown.sh`. Verify with:
```bash
aws lambda list-functions --query 'Functions[?FunctionName==`chat-api-lambda`]'
aws ecr describe-repositories --query 'repositories[?repositoryName==`chat-api`]'
aws secretsmanager describe-secret --secret-id chat-api/llm-api-key
```
All commands should return empty arrays after teardown.

## Failure modes to handle

| Failure | Where | How to handle |
|---------|-------|---------------|
| AWS credentials not configured | deploy.sh | `aws sts get-caller-identity` fails with clear error |
| ECR push auth fails | deploy.sh | `docker login` step; print command to re-authenticate |
| Lambda cold start timeout | Lambda runtime | Set `LAMBDA_TIMEOUT_SECONDS=30`; LLM calls must complete in time |
| Secrets Manager permission denied | src/config.py | Print "Cannot read secret — check IAM role permissions", raise |
| API Gateway 502 | API Gateway | Lambda threw exception; check CloudWatch logs |

## The metric this project measures

**Cold start latency** — p50 and p95 of full invocation time after cold start.
Measured by `scripts/measure_cold_start.py`.
**Lambda execution duration** — visible in CloudWatch metrics as `Duration`.
Target: p95 < 5 seconds for a /health call. LLM generation latency adds on top.

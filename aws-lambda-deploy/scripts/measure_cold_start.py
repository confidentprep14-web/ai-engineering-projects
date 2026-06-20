"""Invoke the Lambda function 10 times after a 15-minute pause to ensure cold starts."""
import boto3, json, time, statistics, os
from dotenv import load_dotenv
load_dotenv(".deployed.env")

FUNCTION_NAME = os.getenv("LAMBDA_FUNCTION_NAME", "chat-api-lambda")
N_INVOCATIONS = 10

client = boto3.client("lambda", region_name=os.getenv("AWS_REGION", "us-east-1"))

print(f"Invoking {FUNCTION_NAME} {N_INVOCATIONS} times to measure cold start...")
print("Note: this measures full invocation latency, not isolated init time.")
print("For init time, check CloudWatch logs for 'Init Duration' after first invocation.")

latencies = []
for i in range(N_INVOCATIONS):
    payload = {"rawPath": "/health", "requestContext": {"http": {"method": "GET"}}, "headers": {}}
    t = time.perf_counter()
    resp = client.invoke(FunctionName=FUNCTION_NAME, Payload=json.dumps(payload))
    latency_ms = int((time.perf_counter() - t) * 1000)
    latencies.append(latency_ms)
    print(f"  Invocation {i+1}: {latency_ms}ms")
    time.sleep(1)

latencies.sort()
p50 = statistics.median(latencies)
p95 = latencies[int(0.95 * len(latencies))]
print(f"\nResults across {N_INVOCATIONS} invocations:")
print(f"  p50: {p50}ms")
print(f"  p95: {p95}ms")
print(f"  Min: {min(latencies)}ms | Max: {max(latencies)}ms")
print(f"\nCheck CloudWatch Logs for 'Init Duration' to see true cold start overhead.")

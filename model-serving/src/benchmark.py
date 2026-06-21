"""Benchmark a SageMaker real-time endpoint with sequential invocations and
report p50/p95/p99 latency.
"""
import argparse
import json
import os
import statistics
import time

import boto3
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

COLUMN_NAMES = [
    "age", "workclass", "fnlwgt", "education", "education_num",
    "marital_status", "occupation", "relationship", "race", "sex",
    "capital_gain", "capital_loss", "hours_per_week", "native_country",
    "income",
]


def create_sample_payload(data_path: str, n_rows: int = 1) -> str:
    """Load `n_rows` rows from adult.data, preprocess them the same way
    training did (column names, strip, dropna, dummy-encode), and return a
    headerless CSV string of the feature row(s) ready to send to the endpoint.
    """
    df = pd.read_csv(
        data_path,
        names=COLUMN_NAMES,
        sep=r",\s*",
        engine="python",
        na_values="?",
    )
    df = df.apply(lambda col: col.str.strip() if col.dtype == "object" else col)
    df = df.dropna()

    X = df.drop(columns=["income"])
    X = pd.get_dummies(X)

    sample = X.head(n_rows)
    return sample.to_csv(index=False, header=False).strip()


def invoke_once(runtime_client, endpoint_name: str, payload: str) -> tuple:
    """Invoke the endpoint once and return (latency_ms, response_body)."""
    t_start = time.monotonic()
    response = runtime_client.invoke_endpoint(
        EndpointName=endpoint_name,
        ContentType="text/csv",
        Body=payload,
    )
    body = response["Body"].read().decode("utf-8")
    t_end = time.monotonic()

    latency_ms = (t_end - t_start) * 1000
    return latency_ms, body


def benchmark_endpoint(endpoint_name: str, data_path: str, n_invocations: int = 100) -> dict:
    """Run `n_invocations` sequential invocations against `endpoint_name`
    using the same single-row payload, and compute p50/p95/p99 latency.
    """
    runtime_client = boto3.client("sagemaker-runtime")
    payload = create_sample_payload(data_path, n_rows=1)

    latencies = []
    for _ in range(n_invocations):
        latency_ms, _ = invoke_once(runtime_client, endpoint_name, payload)
        latencies.append(latency_ms)

    quantiles = statistics.quantiles(latencies, n=100)
    p50 = quantiles[49]
    p95 = quantiles[94]
    p99 = quantiles[98]

    return {
        "p50_ms": p50,
        "p95_ms": p95,
        "p99_ms": p99,
        "n": n_invocations,
        "latencies": latencies,
    }


def print_benchmark_report(results: dict) -> None:
    print(f"Benchmark Results (n={results['n']} invocations)")
    print(f"p50 latency: {results['p50_ms']:.1f} ms")
    print(f"p95 latency: {results['p95_ms']:.1f} ms")
    print(f"p99 latency: {results['p99_ms']:.1f} ms")


def main():
    parser = argparse.ArgumentParser(description="Benchmark a SageMaker real-time endpoint")
    parser.add_argument("--endpoint-name", type=str, required=True)
    parser.add_argument("--n-invocations", type=int, default=100)
    parser.add_argument("--data", type=str, default="data/adult.data")
    args = parser.parse_args()

    results = benchmark_endpoint(args.endpoint_name, args.data, args.n_invocations)
    print_benchmark_report(results)

    os.makedirs("output", exist_ok=True)
    with open("output/latencies.json", "w") as f:
        json.dump(results["latencies"], f)


if __name__ == "__main__":
    main()

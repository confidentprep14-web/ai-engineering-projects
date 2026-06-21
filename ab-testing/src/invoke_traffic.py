"""Send N requests to the A/B endpoint with NO TargetVariant header, so
SageMaker routes traffic internally according to the configured weights, and
track which variant served each response.
"""
import argparse
import json
import os

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


def create_sample_payload(data_path: str) -> str:
    """Build a single-row text/csv payload from the first valid row of
    adult.data, preprocessed the same way as training (dummy-encoded).
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

    row = X.iloc[[0]]
    return row.to_csv(index=False, header=False)


def send_requests(endpoint_name: str, payload: str, n_requests: int) -> dict:
    """Send `n_requests` requests to `endpoint_name` with no TargetVariant
    header, so SageMaker's internal weighted routing decides which variant
    serves each one. Reads response["InvokedProductionVariant"] to track
    which variant actually served the request.

    Returns {"current": int, "challenger": int, "total": int, "ratio": float}
    where ratio = challenger / total.
    """
    runtime = boto3.client("sagemaker-runtime")

    counts = {"current": 0, "challenger": 0}
    for _ in range(n_requests):
        response = runtime.invoke_endpoint(
            EndpointName=endpoint_name,
            ContentType="text/csv",
            Body=payload,
        )
        variant = response["InvokedProductionVariant"]
        counts[variant] = counts.get(variant, 0) + 1

    total = counts["current"] + counts["challenger"]
    ratio = counts["challenger"] / total if total else 0.0

    return {
        "current": counts["current"],
        "challenger": counts["challenger"],
        "total": total,
        "ratio": ratio,
    }


def print_traffic_report(routing: dict) -> None:
    """Print the per-variant routing breakdown as percentages of total."""
    total = routing["total"]
    current = routing["current"]
    challenger = routing["challenger"]

    print(f"Traffic routing over {total} requests:")
    print(f"  current:    {current} ({current / total * 100:.1f}%)")
    print(f"  challenger: {challenger} ({challenger / total * 100:.1f}%)")


def main():
    parser = argparse.ArgumentParser(description="Send traffic to the A/B endpoint and observe routing")
    parser.add_argument("--endpoint-name", type=str, required=True)
    parser.add_argument("--n-requests", type=int, default=1000)
    parser.add_argument("--data", type=str, default="data/adult.data")
    args = parser.parse_args()

    payload = create_sample_payload(args.data)
    routing = send_requests(args.endpoint_name, payload, args.n_requests)
    print_traffic_report(routing)

    os.makedirs("output", exist_ok=True)
    with open("output/traffic_routing.json", "w") as f:
        json.dump(routing, f, indent=2)


if __name__ == "__main__":
    main()

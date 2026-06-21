"""Print an itemised AWS Cost Explorer cost table for the services this
Path 3 build touches: SageMaker, S3, Lambda, Step Functions, SNS, and
CloudWatch.

fetch_cost_by_service is the only AWS-calling function in this file --
one get_cost_and_usage() call, reshaped into a sorted list of dicts.
print_cost_table is pure formatting with zero AWS dependency (see
README.md for the real, non-mocked run of this function with synthetic
inputs).
"""
import argparse
import os
from datetime import datetime, timedelta

import boto3
from dotenv import load_dotenv

load_dotenv()

DASHBOARD_SERVICES = [
    "Amazon SageMaker",
    "Amazon S3",
    "AWS Lambda",
    "AWS Step Functions",
    "Amazon SNS",
    "Amazon CloudWatch",
]


def fetch_cost_by_service(account_id: str, days: int, region: str) -> list:
    """Call Cost Explorer's get_cost_and_usage for the last `days` days,
    grouped by service. Returns a list of {"service": str, "cost_usd":
    float} sorted by cost descending.

    Cost Explorer is a global (not regional) API but the client still
    requires a region_name to construct -- AWS's own convention is
    us-east-1 for this endpoint regardless of where workloads run.
    """
    client = boto3.client("ce", region_name="us-east-1")

    end = datetime.utcnow().date()
    start = end - timedelta(days=days)

    response = client.get_cost_and_usage(
        TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
        Granularity="DAILY",
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        Metrics=["UnblendedCost"],
    )

    totals = {}
    for result in response.get("ResultsByTime", []):
        for group in result.get("Groups", []):
            service = group["Keys"][0]
            cost = float(group["Metrics"]["UnblendedCost"]["Amount"])
            totals[service] = totals.get(service, 0.0) + cost

    costs = [{"service": service, "cost_usd": cost} for service, cost in totals.items()]
    costs.sort(key=lambda c: c["cost_usd"], reverse=True)

    return costs


def print_cost_table(costs: list) -> None:
    """Print the fixed-width cost table. Pure formatting -- zero AWS
    dependency, takes only the list fetch_cost_by_service() returns (or
    any list shaped the same way). Always shows all 6 DASHBOARD_SERVICES
    rows; services missing from `costs` print as $0.0000."""
    cost_by_service = {c["service"]: c["cost_usd"] for c in costs}

    print("AWS Cost Dashboard — Last 24 hours")
    print("=" * 36)
    print(f"{'Service':<28}{'Cost (USD)':>8}")
    print("-" * 36)

    total = 0.0
    for service in DASHBOARD_SERVICES:
        cost = cost_by_service.get(service, 0.0)
        total += cost
        print(f"{service:<28}${cost:.4f}")

    print("-" * 36)
    print(f"{'TOTAL':<28}${total:.4f}")


def main():
    parser = argparse.ArgumentParser(description="Print the AWS Cost Explorer cost dashboard")
    parser.add_argument("--days", type=int, default=1)
    args = parser.parse_args()

    region = os.environ.get("AWS_REGION", "us-east-1")
    account_id = os.environ.get("AWS_ACCOUNT_ID", "")

    try:
        costs = fetch_cost_by_service(account_id, args.days, region)
    except Exception as e:
        error_code = getattr(getattr(e, "response", {}), "get", lambda *_: None)("Error", {}).get("Code") if hasattr(e, "response") else None
        if error_code == "DataUnavailableException" or "not enabled" in str(e).lower():
            print("Cost Explorer not enabled. Enable it in AWS Billing console.")
            costs = []
        else:
            raise

    if args.days == 1 and datetime.utcnow().hour < 6:
        print("Note: it is early in the day (UTC) -- today's costs may be partial.")

    print_cost_table(costs)


if __name__ == "__main__":
    main()

"""Live-update the A/B endpoint's traffic weights without recreating it --
this is how you do a gradual rollout: 90/10 -> 50/50 -> 0/100.
"""
import argparse
import os

import boto3
from dotenv import load_dotenv

load_dotenv()


def validate_weights(current: int, challenger: int) -> None:
    """Raise ValueError if the weights don't sum to 10."""
    total = current + challenger
    if total != 10:
        raise ValueError(f"Weights must sum to 10, got {total}")


def update_traffic_weights(endpoint_name: str, current_weight: int, challenger_weight: int) -> None:
    """Validate weights, then call update_endpoint_weights_and_capacities to
    shift live traffic. No endpoint recreation needed -- the shift takes
    effect within seconds.

    Weight 0 for either variant is valid: 0/10 means 0% of traffic, which is
    how you complete a full rollout to the other variant.
    """
    validate_weights(current_weight, challenger_weight)

    sm = boto3.client("sagemaker")
    sm.update_endpoint_weights_and_capacities(
        EndpointName=endpoint_name,
        DesiredWeightsAndCapacities=[
            {"VariantName": "current", "DesiredWeight": current_weight},
            {"VariantName": "challenger", "DesiredWeight": challenger_weight},
        ],
    )

    print(f"Traffic updated: {current_weight * 10}% current / {challenger_weight * 10}% challenger")


def main():
    parser = argparse.ArgumentParser(description="Shift live traffic weights on the A/B endpoint")
    parser.add_argument("--current-weight", type=int, required=True)
    parser.add_argument("--challenger-weight", type=int, required=True)
    parser.add_argument(
        "--endpoint-name",
        type=str,
        default=os.getenv("SAGEMAKER_ENDPOINT_NAME", "p3-08-ab-endpoint"),
    )
    args = parser.parse_args()

    validate_weights(args.current_weight, args.challenger_weight)
    update_traffic_weights(args.endpoint_name, args.current_weight, args.challenger_weight)


if __name__ == "__main__":
    main()

"""Compute the running cost of the SageMaker endpoint since creation."""
import argparse
import datetime
import os

from dotenv import load_dotenv

load_dotenv()

INSTANCE_PRICES = {
    "ml.m5.large": 0.115,
    "ml.m5.xlarge": 0.23,
    "ml.t2.medium": 0.056,
}


def compute_cost(instance_type: str, created_at_iso: str) -> dict:
    """Compute elapsed hours since `created_at_iso` and the resulting cost
    at `instance_type`'s hourly rate.
    """
    created_at = datetime.datetime.fromisoformat(created_at_iso.replace("Z", "+00:00"))
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=datetime.timezone.utc)

    now = datetime.datetime.now(datetime.timezone.utc)
    elapsed_hours = (now - created_at).total_seconds() / 3600

    cost_usd = elapsed_hours * INSTANCE_PRICES[instance_type]

    return {
        "elapsed_hours": elapsed_hours,
        "cost_usd": cost_usd,
        "instance_type": instance_type,
    }


def main():
    parser = argparse.ArgumentParser(description="Compute running cost of the SageMaker endpoint")
    parser.add_argument(
        "--instance-type",
        type=str,
        default=os.getenv("INFERENCE_INSTANCE_TYPE", "ml.t2.medium"),
    )
    args = parser.parse_args()

    try:
        with open(".endpoint-created-at") as f:
            created_at_iso = f.read().strip()
    except FileNotFoundError:
        print("WARNING: .endpoint-created-at not found; creation time was not recorded. Falling back to now (cost = 0).")
        created_at_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    result = compute_cost(args.instance_type, created_at_iso)

    print(f"Endpoint running for {result['elapsed_hours']:.2f} hours")
    print(f"Instance: {result['instance_type']} (${INSTANCE_PRICES[args.instance_type]}/hr)")
    print(f"Total cost: ${result['cost_usd']:.4f}")


if __name__ == "__main__":
    main()

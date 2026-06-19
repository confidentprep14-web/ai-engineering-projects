"""Estimate SageMaker training job cost from instance type and duration."""

import argparse

INSTANCE_PRICES: dict[str, float] = {
    "ml.m5.large": 0.115,
    "ml.m5.xlarge": 0.23,
    "ml.m5.2xlarge": 0.46,
}


def estimate_cost(instance_type: str, duration_minutes: float) -> float:
    """Return the dollar cost of running `instance_type` for `duration_minutes`.

    Raises ValueError if `instance_type` is not in INSTANCE_PRICES.
    """
    if instance_type not in INSTANCE_PRICES:
        known = ", ".join(sorted(INSTANCE_PRICES))
        raise ValueError(
            f"Unknown instance type '{instance_type}'. Known instance types: {known}"
        )
    hourly_rate = INSTANCE_PRICES[instance_type]
    cost = hourly_rate * (duration_minutes / 60)
    return round(cost, 6)


def format_cost_report(instance_type: str, duration_minutes: float) -> str:
    """Return a one-line human-readable cost report."""
    cost = estimate_cost(instance_type, duration_minutes)
    return (
        f"Instance: {instance_type} | Duration: {duration_minutes:.1f} min | "
        f"Cost: ${cost:.4f}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Estimate SageMaker training job cost")
    parser.add_argument("--instance", required=True, help="Instance type, e.g. ml.m5.large")
    parser.add_argument("--minutes", required=True, type=float, help="Duration in minutes")
    args = parser.parse_args()

    print(format_cost_report(args.instance, args.minutes))


if __name__ == "__main__":
    main()

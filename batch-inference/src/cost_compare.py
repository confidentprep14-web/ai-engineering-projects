"""Compare the cost of a SageMaker Batch Transform job against an equivalent
volume of predictions served from a persistent real-time endpoint.
"""
import argparse

INSTANCE_PRICES = {
    "ml.m5.large": 0.115,
    "ml.m5.xlarge": 0.23,
    "ml.t2.medium": 0.056,
}


def calculate_batch_cost(instance_type: str, duration_minutes: float) -> float:
    """Cost of running `instance_type` for `duration_minutes` minutes."""
    return INSTANCE_PRICES[instance_type] * (duration_minutes / 60)


def calculate_realtime_cost(endpoint_hourly_cost: float, prediction_count: int, rpm: float) -> float:
    """Cost of serving `prediction_count` predictions at `rpm` requests/minute
    from a persistent endpoint billed at `endpoint_hourly_cost` per hour.
    """
    minutes = prediction_count / rpm
    return endpoint_hourly_cost * (minutes / 60)


def format_comparison(batch_cost: float, realtime_cost: float, prediction_count: int) -> str:
    """Render a human-readable batch-vs-real-time cost comparison."""
    cheaper = "Batch" if batch_cost < realtime_cost else "Real-time"
    return (
        f"Batch Transform:  ${batch_cost:.4f} for {prediction_count} predictions\n"
        f"Real-time endpoint (estimated): ${realtime_cost:.4f} for same volume\n"
        f"Cheaper option: {cheaper}\n"
        f"Rule of thumb: Batch is cheaper for infrequent, large-volume jobs. Real-time is\n"
        f"necessary for <1s latency requirements."
    )


def main():
    parser = argparse.ArgumentParser(description="Compare batch vs real-time inference cost")
    parser.add_argument("--batch-duration-minutes", type=float, required=True)
    parser.add_argument("--instance-type", type=str, required=True, choices=list(INSTANCE_PRICES))
    parser.add_argument("--prediction-count", type=int, default=9769)
    parser.add_argument("--estimated-rpm", type=float, default=100)
    parser.add_argument("--endpoint-hourly-cost", type=float, default=0.056)
    args = parser.parse_args()

    batch_cost = calculate_batch_cost(args.instance_type, args.batch_duration_minutes)
    realtime_cost = calculate_realtime_cost(
        args.endpoint_hourly_cost, args.prediction_count, args.estimated_rpm
    )

    print(format_comparison(batch_cost, realtime_cost, args.prediction_count))


if __name__ == "__main__":
    main()

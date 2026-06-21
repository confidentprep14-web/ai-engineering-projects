"""Create an hourly SageMaker Model Monitor schedule that compares captured
endpoint traffic against the baseline computed in compute_baseline.py.

SageMaker's minimum monitoring cadence is hourly (cron granularity floor) --
see GUIDE.md for what that means for low-traffic endpoints.
"""
import argparse
import os

from dotenv import load_dotenv

load_dotenv()

HOURLY_CRON_EXPRESSION = "cron(0 * ? * * *)"


def create_monitoring_schedule(
    endpoint_name: str,
    schedule_name: str,
    baseline_s3_uri: str,
    output_s3_uri: str,
    role_arn: str,
) -> str:
    """Create an hourly monitoring schedule via DefaultModelMonitor and
    return the schedule's ARN.
    """
    from sagemaker.model_monitor import DefaultModelMonitor

    monitor = DefaultModelMonitor(role=role_arn)

    baseline_s3_uri = baseline_s3_uri.rstrip("/")

    monitor.create_monitoring_schedule(
        monitor_schedule_name=schedule_name,
        endpoint_input=endpoint_name,
        output_s3_uri=output_s3_uri,
        statistics=baseline_s3_uri + "/statistics.json",
        constraints=baseline_s3_uri + "/constraints.json",
        schedule_cron_expression=HOURLY_CRON_EXPRESSION,
    )

    return monitor.monitoring_schedule_arn


def main():
    parser = argparse.ArgumentParser(description="Create an hourly SageMaker Model Monitor schedule")
    parser.add_argument("--endpoint-name", type=str, default=os.getenv("ENDPOINT_NAME"))
    args = parser.parse_args()

    if not args.endpoint_name:
        raise ValueError("--endpoint-name is required (or set ENDPOINT_NAME in .env)")

    role_arn = os.environ["SAGEMAKER_ROLE_ARN"]
    schedule_name = os.environ["MONITORING_SCHEDULE_NAME"]
    baseline_s3_uri = os.environ["S3_BASELINE_PATH"]
    output_s3_uri = os.environ["S3_MONITORING_RESULTS_PATH"]

    arn = create_monitoring_schedule(
        args.endpoint_name, schedule_name, baseline_s3_uri, output_s3_uri, role_arn
    )

    with open(".schedule-arn", "w") as f:
        f.write(arn)

    print(f"Monitoring schedule created: {schedule_name}")
    print(f"Schedule ARN: {arn}")
    print("Note: first monitoring report will be generated in up to 1 hour.")


if __name__ == "__main__":
    main()

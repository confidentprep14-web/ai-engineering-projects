"""CLI entry point for the weekly model performance report.

Designed to run unattended as a cron job: no interactive prompts, a clear
exit code (0 success, 1 failure), and exceptions caught at the top level so
a cron run never leaves a stack trace on stdout or a half-written report.
"""
import argparse
import json
import os
import sys

import mlflow
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))

import baseline_fetcher  # noqa: E402
import cloudwatch_fetcher  # noqa: E402
import live_evaluator  # noqa: E402
import reporter  # noqa: E402

load_dotenv()

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def load_fixtures() -> tuple[dict, dict, dict]:
    """Load dry-run fixture data so the full pipeline can be exercised with
    zero AWS credentials and no live MLflow server.

    Returns (cloudwatch_metrics, live_eval, baseline).
    """
    with open(os.path.join(FIXTURES_DIR, "sample_cloudwatch_response.json")) as f:
        cloudwatch_metrics = json.load(f)

    with open(os.path.join(FIXTURES_DIR, "sample_monitoring_metrics.json")) as f:
        live_eval = json.load(f)

    baseline = {
        "val_auc": 0.883,
        "val_accuracy": 0.872,
        "run_id": "fixture_run",
        "model_name": "adult-income-xgboost",
        "alias": "production",
    }

    return cloudwatch_metrics, live_eval, baseline


def parse_args():
    parser = argparse.ArgumentParser(description="Generate the weekly model performance report")
    parser.add_argument(
        "--endpoint-name",
        type=str,
        default=os.getenv("DEFAULT_ENDPOINT_NAME", "p3-07-adult-income-endpoint"),
    )
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument(
        "--output",
        type=str,
        default=os.getenv("REPORT_OUTPUT_PATH", "output/report.md"),
    )
    parser.add_argument("--dry-run", action="store_true", default=os.getenv("DRY_RUN", "false").lower() == "true")
    parser.add_argument("--sample-size", type=int, default=200)
    return parser.parse_args()


def main():
    args = parse_args()

    if args.dry_run:
        cloudwatch_metrics, live_eval, baseline = load_fixtures()
    else:
        region = os.getenv("AWS_REGION", "us-east-1")
        mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
        model_name = os.getenv("MLFLOW_MODEL_NAME", "adult-income-xgboost")

        cloudwatch_metrics = cloudwatch_fetcher.fetch_endpoint_metrics(
            args.endpoint_name, args.days, region
        )
        live_eval = live_evaluator.evaluate_endpoint(
            args.endpoint_name, "data/adult.data", args.sample_size
        )
        baseline = baseline_fetcher.get_baseline_from_registry(model_name, "production")

    reporter.generate_weekly_report(cloudwatch_metrics, live_eval, baseline, args.output)
    print(f"Report written to {args.output}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 -- top-level guard for cron safety
        print(f"Error: {exc}")
        sys.exit(1)

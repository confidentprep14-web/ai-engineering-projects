"""Fetch per-variant CloudWatch invocation counts, apply the AUC-improvement
decision rule, and write the promote/keep decision to output/ab_decision.json.
"""
import argparse
import datetime
import json
import os

import boto3
import mlflow
from dotenv import load_dotenv

load_dotenv()


def fetch_variant_invocations(endpoint_name: str, variant_name: str, hours: int = 2) -> dict:
    """Sum the AWS/SageMaker "Invocations" metric for `variant_name` over the
    last `hours` hours.

    Returns {"variant": variant_name, "invocation_count": int}.
    """
    cw = boto3.client("cloudwatch")
    end_time = datetime.datetime.now(datetime.timezone.utc)
    start_time = end_time - datetime.timedelta(hours=hours)

    response = cw.get_metric_statistics(
        Namespace="AWS/SageMaker",
        MetricName="Invocations",
        Dimensions=[
            {"Name": "EndpointName", "Value": endpoint_name},
            {"Name": "VariantName", "Value": variant_name},
        ],
        StartTime=start_time,
        EndTime=end_time,
        Period=3600,
        Statistics=["Sum"],
    )

    invocation_count = int(sum(dp["Sum"] for dp in response.get("Datapoints", [])))
    return {"variant": variant_name, "invocation_count": invocation_count}


def apply_decision_rule(challenger_auc: float, baseline_auc: float, threshold: float = 0.01) -> dict:
    """Decide whether to deploy the challenger: it must beat baseline by more
    than `threshold` AUC.

    Returns {"deploy_challenger": bool, "reason": str, "delta": float}.
    """
    delta = challenger_auc - baseline_auc
    deploy_challenger = delta > threshold

    if deploy_challenger:
        reason = (
            f"Challenger AUC {challenger_auc:.3f} exceeds baseline {baseline_auc:.3f} "
            f"by {delta:.3f} (threshold {threshold:.3f}) → deploy challenger"
        )
    else:
        reason = (
            f"Challenger AUC {challenger_auc:.3f} does not exceed baseline {baseline_auc:.3f} "
            f"by threshold {threshold:.3f} → keep current"
        )

    return {"deploy_challenger": deploy_challenger, "reason": reason, "delta": delta}


def _read_baseline_auc(model_name: str) -> float:
    """Fall back to the val_auc metric logged on the "production" run when
    --baseline-auc isn't passed on the CLI.
    """
    client = mlflow.MlflowClient()
    version = client.get_model_version_by_alias(model_name, "production")
    run = client.get_run(version.run_id)
    return run.data.metrics["val_auc"]


def _read_challenger_auc() -> float:
    """Read the challenger's val_AUC written by prepare_variants.py."""
    if not os.path.exists(".challenger-auc"):
        raise FileNotFoundError(
            "Challenger AUC not recorded -- run python src/prepare_variants.py first."
        )
    with open(".challenger-auc") as f:
        return float(f.read().strip())


def main():
    parser = argparse.ArgumentParser(description="Evaluate the A/B test and decide the winner")
    parser.add_argument("--endpoint-name", type=str, required=True)
    parser.add_argument("--baseline-auc", type=float, default=None)
    args = parser.parse_args()

    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    model_name = os.getenv("MLFLOW_MODEL_NAME", "adult-income-xgboost")
    threshold = float(os.getenv("AUC_IMPROVEMENT_THRESHOLD", "0.01"))

    baseline_auc = args.baseline_auc if args.baseline_auc is not None else _read_baseline_auc(model_name)
    challenger_auc = _read_challenger_auc()

    current_metrics = fetch_variant_invocations(args.endpoint_name, "current")
    challenger_metrics = fetch_variant_invocations(args.endpoint_name, "challenger")

    for metrics in (current_metrics, challenger_metrics):
        if metrics["invocation_count"] == 0:
            print("Not enough traffic yet — run invoke_traffic.py first")

    decision = apply_decision_rule(challenger_auc, baseline_auc, threshold)

    winner = "challenger" if decision["deploy_challenger"] else "current"
    print(f"Winner: {winner}")
    print(f"Current AUC (baseline): {baseline_auc:.4f}")
    print(f"Challenger AUC:         {challenger_auc:.4f}")
    print(decision["reason"])

    result = {
        "winner": winner,
        "baseline_auc": baseline_auc,
        "challenger_auc": challenger_auc,
        "current_invocations": current_metrics["invocation_count"],
        "challenger_invocations": challenger_metrics["invocation_count"],
        **decision,
    }

    os.makedirs("output", exist_ok=True)
    with open("output/ab_decision.json", "w") as f:
        json.dump(result, f, indent=2)


if __name__ == "__main__":
    main()

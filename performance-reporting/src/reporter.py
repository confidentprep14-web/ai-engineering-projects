"""Compute the current-vs-baseline delta and render the weekly Markdown
performance report.
"""
import os
from datetime import datetime

OK_WARNING_THRESHOLD = 0.02


def compute_delta(current_metric: float | None, baseline_metric: float | None) -> dict:
    """Compare a current metric to its baseline.

    Returns:
        {"delta": float, "direction": str, "percent_change": float}

    If either input is None, the comparison is meaningless -- returns
    {"delta": None, "direction": "unknown", "percent_change": None}.
    """
    if current_metric is None or baseline_metric is None:
        return {"delta": None, "direction": "unknown", "percent_change": None}

    delta = current_metric - baseline_metric

    if delta > 0:
        direction = "improvement"
    elif delta < 0:
        direction = "regression"
    else:
        direction = "no change"

    percent_change = (delta / baseline_metric) * 100 if baseline_metric != 0 else None

    return {"delta": delta, "direction": direction, "percent_change": percent_change}


def _status(live_auc: float | None, baseline_auc: float | None) -> str:
    """OK if current AUC is within OK_WARNING_THRESHOLD of baseline; WARNING
    if it drops more than that below baseline; UNKNOWN if either metric is
    unavailable.
    """
    if live_auc is None or baseline_auc is None:
        return "UNKNOWN"

    if baseline_auc - live_auc > OK_WARNING_THRESHOLD:
        return "WARNING"

    return "OK"


def _recommendation(status: str, delta_info: dict) -> str:
    if status == "OK":
        return (
            "Live AUC is within the expected range of the registered baseline. "
            "No action needed -- continue routine weekly monitoring."
        )
    if status == "WARNING":
        delta = delta_info.get("delta")
        delta_str = f"{delta:+.4f}" if delta is not None else "N/A"
        return (
            f"Live AUC has dropped {delta_str} relative to baseline, exceeding the "
            f"±{OK_WARNING_THRESHOLD:.2f} threshold. Investigate data drift, "
            "label distribution shifts, or upstream feature changes. Consider "
            "retraining if the drop persists across multiple weekly reports."
        )
    return (
        "Baseline or live evaluation metrics were not available this run, so "
        "no comparison could be made. Check that the MLflow \"production\" alias "
        "is registered and that the endpoint evaluation completed successfully."
    )


def generate_weekly_report(
    cloudwatch_metrics: dict, live_eval: dict, baseline: dict, output_path: str
) -> str:
    """Render the weekly Markdown performance report and write it to
    `output_path` via an atomic write (temp file + os.replace) so a crash
    mid-write never leaves a partial report file on disk.

    Returns the report text.
    """
    endpoint_name = cloudwatch_metrics.get("endpoint_name") or live_eval.get("endpoint_name", "unknown")
    n_days = cloudwatch_metrics.get("period_days", 7)

    live_auc = live_eval.get("auc")
    live_accuracy = live_eval.get("accuracy")
    baseline_auc = baseline.get("val_auc")
    baseline_accuracy = baseline.get("val_accuracy")

    auc_delta_info = compute_delta(live_auc, baseline_auc)
    accuracy_delta_info = compute_delta(live_accuracy, baseline_accuracy)

    status = _status(live_auc, baseline_auc)

    auc_delta_str = f"{auc_delta_info['delta']:+.4f}" if auc_delta_info["delta"] is not None else "N/A"
    accuracy_delta_str = (
        f"{accuracy_delta_info['delta']:+.4f}" if accuracy_delta_info["delta"] is not None else "N/A"
    )

    live_auc_str = f"{live_auc:.4f}" if live_auc is not None else "N/A"
    baseline_auc_str = f"{baseline_auc:.4f}" if baseline_auc is not None else "N/A"
    live_accuracy_str = f"{live_accuracy:.4f}" if live_accuracy is not None else "N/A"
    baseline_accuracy_str = f"{baseline_accuracy:.4f}" if baseline_accuracy is not None else "N/A"

    invocation_count = cloudwatch_metrics.get("invocation_count", 0)
    latency_ms = cloudwatch_metrics.get("model_latency_p50_ms", 0.0)
    error_count = cloudwatch_metrics.get("error_count", 0)
    error_rate = cloudwatch_metrics.get("error_rate", 0.0)

    n_samples = live_eval.get("n_samples", 0)

    model_name = baseline.get("model_name", "unknown")
    alias = baseline.get("alias", "production")
    run_id = baseline.get("run_id") or "N/A"

    recommendation = _recommendation(status, auc_delta_info)

    report = f"""# Weekly Model Performance Report
Generated: {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}
Endpoint: {endpoint_name}
Period: Last {n_days} days

## Summary

| Metric | Current | Baseline | Delta |
|---|---|---|---|
| AUC | {live_auc_str} | {baseline_auc_str} | {auc_delta_str} |
| Accuracy | {live_accuracy_str} | {baseline_accuracy_str} | {accuracy_delta_str} |

**Status:** {status}
- OK: current AUC within 0.02 of baseline
- WARNING: current AUC drops more than 0.02 below baseline
- UNKNOWN: baseline or live metrics not available

## Endpoint Health (CloudWatch)

| Metric | Value |
|---|---|
| Invocations (last {n_days}d) | {invocation_count} |
| Avg Model Latency | {latency_ms:.1f} ms |
| Error Count | {error_count} |
| Error Rate | {error_rate:.2%} |

## Live Evaluation

Evaluated {n_samples} samples from held-out test set.
- AUC: {live_auc_str}
- Accuracy: {live_accuracy_str}

## Baseline (MLflow Registry)

- Model: {model_name} @ {alias}
- Run ID: {run_id}
- Baseline val_AUC: {baseline_auc_str}

## Recommendation

{recommendation}
"""

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    tmp_path = f"{output_path}.tmp"
    with open(tmp_path, "w") as f:
        f.write(report)
    os.replace(tmp_path, output_path)

    return report

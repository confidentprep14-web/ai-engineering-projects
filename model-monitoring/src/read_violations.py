"""Fetch the latest SageMaker Model Monitor violation report from S3 (or a
local JSON file for testing) and print plain-English explanations of what
drifted and by how much.
"""
import argparse
import json
import os

from dotenv import load_dotenv

load_dotenv()


def fetch_latest_report(monitoring_results_s3: str) -> dict:
    """List S3 objects under monitoring_results_s3, find the most recently
    modified JSON file, download and parse it.

    Returns the parsed dict. Raises FileNotFoundError (with the spec's
    "wait up to 1 hour" message) if no monitoring report exists yet.
    """
    import boto3

    assert monitoring_results_s3.startswith("s3://"), (
        f"monitoring_results_s3 must be an s3:// URI, got {monitoring_results_s3}"
    )
    bucket, _, prefix = monitoring_results_s3[len("s3://"):].partition("/")

    s3 = boto3.client("s3")
    paginator = s3.get_paginator("list_objects_v2")

    json_objects = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".json"):
                json_objects.append(obj)

    if not json_objects:
        raise FileNotFoundError(
            "No monitoring report yet. Wait up to 1 hour after schedule creation."
        )

    latest = max(json_objects, key=lambda obj: obj["LastModified"])
    response = s3.get_object(Bucket=bucket, Key=latest["Key"])
    return json.loads(response["Body"].read())


def parse_violation(violation: dict) -> str:
    """Convert a single SageMaker monitoring violation dict to a
    plain-English string.
    """
    feature_name = violation.get("feature_name", "<unknown feature>")
    check_type = violation.get("constraint_check_type", "")
    metric = violation.get("metric", {})
    threshold = metric.get("threshold")
    observed = metric.get("observed_value")

    if check_type == "distribution_non_parametric_significance":
        test_name = "non-parametric significance test"
        return (
            f"Feature '{feature_name}': distribution shifted significantly.\n"
            f"  Test: {test_name}\n"
            f"  Expected p-value > {threshold}, observed p-value = {observed}\n"
            f"  Interpretation: The distribution of '{feature_name}' in recent traffic "
            "is unlikely to match training data."
        )

    return (
        f"Feature '{feature_name}': {violation.get('description', 'constraint violation')}.\n"
        f"  Check: {check_type}\n"
        f"  Expected threshold {threshold}, observed value = {observed}"
    )


def parse_monitoring_report(report: dict) -> list:
    """Extract the violations list from the report and convert each to a
    plain-English string.
    """
    violations = report.get("violations", [])
    return [parse_violation(v) for v in violations]


def main():
    parser = argparse.ArgumentParser(description="Read and explain the latest Model Monitor violation report")
    parser.add_argument("--s3-path", type=str, default=os.getenv("S3_MONITORING_RESULTS_PATH"))
    parser.add_argument("--local-file", type=str, default=None)
    args = parser.parse_args()

    if args.local_file:
        with open(args.local_file) as f:
            report = json.load(f)
    else:
        if not args.s3_path:
            raise ValueError("--s3-path is required (or set S3_MONITORING_RESULTS_PATH in .env), or pass --local-file")
        try:
            report = fetch_latest_report(args.s3_path)
        except FileNotFoundError as e:
            print(str(e))
            return

    if "violations" not in report:
        print("Monitoring violation JSON has an unexpected structure (missing 'violations' key).")
        print(json.dumps(report, indent=2))
        print("Please report this issue.")
        return

    explanations = parse_monitoring_report(report)

    if not explanations:
        print("No violations found. Features within expected distribution.")
        return

    print(f"Model Monitor Report — {len(explanations)} violation(s) found")
    print("=" * 40)
    for i, explanation in enumerate(explanations):
        print(explanation)
        if i < len(explanations) - 1:
            print("-" * 40)


if __name__ == "__main__":
    main()

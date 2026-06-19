"""CLI entry point for the data exploration / EDA pipeline."""
import argparse
import sys

from analyzer import (
    compute_class_balance,
    compute_correlations,
    compute_feature_stats,
    compute_missing_counts,
    flag_high_missing,
)
from loader import load_adult_dataset
from reporter import generate_markdown_report


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="EDA pipeline for the UCI Adult Income dataset.")
    parser.add_argument("--data", required=True, help="Path to the adult.data CSV file.")
    parser.add_argument("--output", required=True, help="Path to write the Markdown report.")
    parser.add_argument(
        "--missing-threshold",
        type=float,
        default=0.2,
        help="Fraction-missing threshold above which a column is flagged for imputation (default: 0.2).",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    df = load_adult_dataset(args.data)

    class_balance = compute_class_balance(df)
    feature_stats = compute_feature_stats(df)
    missing_counts = compute_missing_counts(df)
    correlations = compute_correlations(df)
    high_missing = flag_high_missing(missing_counts, threshold=args.missing_threshold)

    stats = {
        "class_balance": class_balance,
        "feature_stats": feature_stats,
        "missing_counts": missing_counts,
        "correlations": correlations,
        "high_missing": high_missing,
        "threshold": args.missing_threshold,
    }

    generate_markdown_report(df, stats, args.output)

    print(f"Report written to {args.output} ({len(df)} rows, {len(df.columns)} columns)")
    flagged_str = ", ".join(high_missing) if high_missing else "none"
    print(f"Flagged for imputation: {flagged_str}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

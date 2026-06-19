"""Render EDA statistics into a structured Markdown data quality report."""
import os

import pandas as pd

from analyzer import find_most_correlated_pair


def generate_markdown_report(df: pd.DataFrame, stats: dict, output_path: str) -> None:
    """Write a Markdown data quality report to output_path.

    `stats` is expected to contain:
        class_balance: dict
        feature_stats: dict (numeric / categorical)
        missing_counts: dict
        correlations: pd.DataFrame
        high_missing: list[str]
        threshold: float
    """
    parent = os.path.dirname(output_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    lines = []
    lines.append("# Data Quality Report — UCI Adult Income")
    lines.append("")

    # Dataset Overview
    lines.append("## Dataset Overview")
    lines.append(f"- Rows: {len(df)}")
    lines.append(f"- Columns: {len(df.columns)}")
    numeric_cols = [c for c in stats["feature_stats"]["numeric"]]
    categorical_cols = [c for c in stats["feature_stats"]["categorical"]]
    lines.append(f"- Numeric columns: {numeric_cols}")
    lines.append(f"- Categorical columns: {categorical_cols}")
    lines.append("")

    # Class Balance
    class_balance = stats["class_balance"]
    lines.append("## Class Balance")
    lines.append("| Label | Count | Fraction |")
    lines.append("|---|---|---|")
    counts = df["income"].value_counts()
    for label in ["<=50K", ">50K"]:
        n = int(counts.get(label, 0))
        frac = class_balance.get(label, 0.0)
        lines.append(f"| {label} | {n} | {frac:.3f} |")
    lines.append("")
    majority = max(class_balance.values()) if class_balance else 0.0
    minority = min(class_balance.values()) if class_balance else 0.0
    ratio = (majority / minority) if minority > 0 else 0.0
    lines.append(f"**Imbalance ratio:** {ratio:.2f}:1")
    lines.append("")

    # Feature Statistics
    lines.append("## Feature Statistics")
    lines.append("")
    lines.append("### Numeric Features")
    lines.append("| Column | Mean | Std | Min | Median | Max |")
    lines.append("|---|---|---|---|---|---|")
    for col, s in stats["feature_stats"]["numeric"].items():
        lines.append(
            f"| {col} | {s['mean']:.2f} | {s['std']:.2f} | {s['min']:.2f} "
            f"| {s['median']:.2f} | {s['max']:.2f} |"
        )
    lines.append("")
    lines.append("### Categorical Features")
    lines.append("| Column | Top Value | Top Count | Unique Values |")
    lines.append("|---|---|---|---|")
    for col, s in stats["feature_stats"]["categorical"].items():
        top_values = s["top_values"]
        if top_values:
            top_value, top_count = next(iter(top_values.items()))
        else:
            top_value, top_count = "", 0
        n_unique = df[col].nunique(dropna=True)
        lines.append(f"| {col} | {top_value} | {top_count} | {n_unique} |")
    lines.append("")

    # Missing Values
    lines.append("## Missing Values")
    lines.append("| Column | Missing Count | Missing Fraction |")
    lines.append("|---|---|---|")
    for col, s in stats["missing_counts"].items():
        lines.append(f"| {col} | {s['count']} | {s['fraction']:.3f} |")
    lines.append("")

    # Correlation
    lines.append("## Correlation (Numeric Features)")
    corr_df = stats["correlations"]
    if corr_df is None or corr_df.empty:
        lines.append("Correlation: insufficient numeric columns.")
    else:
        col_a, col_b, value = find_most_correlated_pair(corr_df)
        lines.append(f"Most correlated pair: {col_a} ↔ {col_b} (r = {value:.3f})")
        lines.append("")
        header_cols = list(corr_df.columns)
        lines.append("| | " + " | ".join(header_cols) + " |")
        lines.append("|---|" + "---|" * len(header_cols))
        for row_label in corr_df.index:
            row_values = " | ".join(f"{corr_df.loc[row_label, c]:.3f}" for c in header_cols)
            lines.append(f"| {row_label} | {row_values} |")
    lines.append("")

    # Data Quality Flags
    lines.append("## Data Quality Flags")
    threshold = stats.get("threshold", 0.2)
    high_missing = stats.get("high_missing", [])
    lines.append(f"Columns flagged for imputation strategy (>{threshold * 100:.0f}% missing):")
    if high_missing:
        for col in high_missing:
            lines.append(f"- {col}")
    else:
        lines.append("None — all columns below threshold")
    lines.append("")

    with open(output_path, "w") as f:
        f.write("\n".join(lines))

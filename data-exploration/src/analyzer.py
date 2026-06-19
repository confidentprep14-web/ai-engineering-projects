"""Compute EDA statistics for the UCI Adult Income dataset."""
import pandas as pd

from loader import CATEGORICAL_COLUMNS, NUMERIC_COLUMNS


def compute_class_balance(df: pd.DataFrame) -> dict:
    """Return the fraction of rows in each income class.

    Returns {"<=50K": float, ">50K": float}, values sum to 1.0.
    """
    if "income" not in df.columns:
        raise KeyError("income column not found")

    fractions = df["income"].value_counts(normalize=True)
    return {label: float(frac) for label, frac in fractions.items()}


def compute_feature_stats(df: pd.DataFrame) -> dict:
    """Compute per-feature statistics for numeric and categorical columns.

    Returns {"numeric": {col: {...}}, "categorical": {col: {...}}}.
    """
    numeric_stats = {}
    for col in NUMERIC_COLUMNS:
        if col not in df.columns:
            continue
        series = df[col]
        numeric_stats[col] = {
            "mean": float(series.mean()),
            "std": float(series.std()),
            "min": float(series.min()),
            "max": float(series.max()),
            "median": float(series.median()),
        }

    categorical_stats = {}
    for col in CATEGORICAL_COLUMNS:
        if col not in df.columns:
            continue
        top_values = df[col].value_counts().head(5)
        categorical_stats[col] = {
            "top_values": {str(k): int(v) for k, v in top_values.items()}
        }

    return {"numeric": numeric_stats, "categorical": categorical_stats}


def compute_missing_counts(df: pd.DataFrame) -> dict:
    """Return {col: {"count": int, "fraction": float}} for ALL columns."""
    n_rows = len(df)
    result = {}
    for col in df.columns:
        count = int(df[col].isna().sum())
        fraction = count / n_rows if n_rows else 0.0
        result[col] = {"count": count, "fraction": fraction}
    return result


def compute_correlations(df: pd.DataFrame) -> pd.DataFrame:
    """Compute the Pearson correlation matrix on numeric columns only.

    Returns an empty DataFrame if fewer than 2 numeric columns are present.
    """
    numeric_cols = [col for col in df.columns if col in NUMERIC_COLUMNS]
    if len(numeric_cols) < 2:
        return pd.DataFrame()
    return df[numeric_cols].corr()


def flag_high_missing(missing_counts: dict, threshold: float = 0.2) -> list:
    """Return column names where fraction missing exceeds threshold, sorted alphabetically."""
    flagged = [
        col for col, stats in missing_counts.items() if stats["fraction"] > threshold
    ]
    return sorted(flagged)


def find_most_correlated_pair(corr_df: pd.DataFrame):
    """Find the highest absolute correlation between two distinct columns.

    Returns (col_a, col_b, signed_correlation_value).
    Returns ("", "", 0.0) if corr_df is empty.
    """
    if corr_df.empty:
        return ("", "", 0.0)

    best_pair = ("", "", 0.0)
    best_abs = -1.0
    columns = list(corr_df.columns)
    for i, col_a in enumerate(columns):
        for col_b in columns[i + 1:]:
            value = float(corr_df.loc[col_a, col_b])
            if abs(value) > best_abs:
                best_abs = abs(value)
                best_pair = (col_a, col_b, value)

    return best_pair

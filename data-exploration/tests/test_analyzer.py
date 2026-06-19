"""Tests for src/analyzer.py."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from analyzer import (  # noqa: E402
    compute_class_balance,
    compute_correlations,
    compute_feature_stats,
    compute_missing_counts,
    find_most_correlated_pair,
    flag_high_missing,
)


def _fixture_df():
    """10-row fixture with known income counts: 7x '<=50K', 3x '>50K'."""
    return pd.DataFrame(
        {
            "age": [25, 30, 35, 40, 45, 50, 55, 60, 65, 70],
            "fnlwgt": [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000],
            "workclass": ["Private"] * 9 + [np.nan],
            "income": ["<=50K"] * 7 + [">50K"] * 3,
        }
    )


def test_class_balance_sums_to_one():
    df = _fixture_df()
    result = compute_class_balance(df)

    assert abs(sum(result.values()) - 1.0) < 1e-9
    assert len(result) == 2
    assert abs(result["<=50K"] - 0.7) < 1e-9
    assert abs(result[">50K"] - 0.3) < 1e-9


def test_class_balance_missing_income_raises_key_error():
    df = pd.DataFrame({"age": [1, 2, 3]})
    with pytest.raises(KeyError):
        compute_class_balance(df)


def test_flag_high_missing_threshold():
    missing_counts = {
        "occupation": {"count": 25, "fraction": 0.25},
        "age": {"count": 10, "fraction": 0.10},
    }
    result = flag_high_missing(missing_counts, threshold=0.2)

    assert result == ["occupation"]


def test_flag_high_missing_returns_empty_when_none_exceed():
    missing_counts = {
        "occupation": {"count": 5, "fraction": 0.05},
        "age": {"count": 10, "fraction": 0.10},
    }
    result = flag_high_missing(missing_counts, threshold=0.2)

    assert result == []


def test_report_file_written_and_non_empty(tmp_path):
    repo_root = os.path.join(os.path.dirname(__file__), "..")
    data_path = os.path.join(repo_root, "data", "adult.data")
    if not os.path.exists(data_path):
        pytest.skip("real dataset not downloaded at data/adult.data")

    sys.path.insert(0, os.path.join(repo_root, "src"))
    import main  # noqa: E402

    output_path = os.path.join(tmp_path, "report.md")
    main.main(["--data", data_path, "--output", output_path])

    assert os.path.exists(output_path)
    assert os.path.getsize(output_path) > 500

    with open(output_path) as f:
        content = f.read()
    assert "## Class Balance" in content


def test_compute_feature_stats_shapes():
    df = _fixture_df()
    stats = compute_feature_stats(df)

    assert "numeric" in stats
    assert "categorical" in stats
    assert "age" in stats["numeric"]
    assert set(stats["numeric"]["age"].keys()) == {"mean", "std", "min", "max", "median"}
    assert "workclass" in stats["categorical"]
    assert "top_values" in stats["categorical"]["workclass"]


def test_compute_missing_counts_includes_all_columns():
    df = _fixture_df()
    result = compute_missing_counts(df)

    assert set(result.keys()) == set(df.columns)
    assert result["workclass"]["count"] == 1
    assert abs(result["workclass"]["fraction"] - 0.1) < 1e-9
    assert result["age"]["count"] == 0


def test_compute_correlations_shape():
    df = _fixture_df()
    corr = compute_correlations(df)

    numeric_cols = ["age", "fnlwgt"]
    assert corr.shape == (len(numeric_cols), len(numeric_cols))


def test_compute_correlations_empty_when_fewer_than_two_numeric():
    df = pd.DataFrame({"workclass": ["a", "b", "c"]})
    corr = compute_correlations(df)

    assert corr.empty


def test_find_most_correlated_pair():
    df = pd.DataFrame(
        {
            "a": [1, 2, 3, 4, 5],
            "b": [2, 4, 6, 8, 10],
            "c": [5, 3, 4, 1, 2],
        }
    )
    corr = df.corr()
    col_a, col_b, value = find_most_correlated_pair(corr)

    assert {col_a, col_b} == {"a", "b"}
    assert abs(value - 1.0) < 1e-9


def test_find_most_correlated_pair_empty_returns_default():
    empty_corr = pd.DataFrame()
    result = find_most_correlated_pair(empty_corr)

    assert result == ("", "", 0.0)

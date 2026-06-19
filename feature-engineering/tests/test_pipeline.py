"""Tests for src/pipeline.py — the sklearn preprocessing pipeline."""

import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pipeline import build_pipeline, fit_and_transform, transform

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA_PATH = os.path.join(PROJECT_ROOT, "data", "raw.csv")

COLUMN_NAMES = [
    "age", "workclass", "fnlwgt", "education", "education-num",
    "marital-status", "occupation", "relationship", "race", "sex",
    "capital-gain", "capital-loss", "hours-per-week", "native-country", "income",
]


def _load_slice(n_rows: int) -> pd.DataFrame:
    """Load the first n_rows of the raw dataset as a labeled DataFrame, X only."""
    df = pd.read_csv(DATA_PATH, header=None, skipinitialspace=True, nrows=n_rows)
    df.columns = COLUMN_NAMES

    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].str.strip()
            df[col] = df[col].replace("?", np.nan)

    return df.drop(columns=["income"])


def test_pipeline_output_has_no_nan():
    X = _load_slice(50)

    # Inject NaN into several cells to simulate "?" replacement.
    X.loc[0, "workclass"] = np.nan
    X.loc[1, "occupation"] = np.nan
    X.loc[2, "age"] = np.nan

    pipeline = build_pipeline()
    result = fit_and_transform(pipeline, X)

    assert not np.isnan(result).any()


def test_pipeline_output_shape_is_non_zero():
    X = _load_slice(50)
    X.loc[0, "workclass"] = np.nan
    X.loc[1, "occupation"] = np.nan
    X.loc[2, "age"] = np.nan

    pipeline = build_pipeline()
    result = fit_and_transform(pipeline, X)

    assert result.shape[0] == 50
    assert result.shape[1] > 14


def test_joblib_roundtrip_preserves_transform(tmp_path):
    import joblib

    X_train = _load_slice(100)
    X_new = _load_slice(110).iloc[100:110]

    pipeline = build_pipeline()
    fit_and_transform(pipeline, X_train)

    save_path = tmp_path / "pipeline.joblib"
    joblib.dump(pipeline, save_path)

    loaded_pipeline = joblib.load(save_path)
    result = transform(loaded_pipeline, X_new)

    assert not np.isnan(result).any()
    assert result.shape[0] == 10


def test_local_and_sagemaker_use_same_script():
    main_path = os.path.join(PROJECT_ROOT, "src", "main.py")
    assert os.path.exists(main_path)

    with open(main_path) as f:
        contents = f.read()

    assert "--input" in contents
    assert "validate_input" in contents

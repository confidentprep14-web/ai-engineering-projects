import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import inject_drift  # noqa: E402

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "adult.data")


def test_drifted_values_are_outside_expected_range():
    feature_stats = inject_drift.compute_feature_stats(DATA_PATH)
    age_stats = feature_stats["age"]

    drifted_row = inject_drift.create_drifted_row(feature_stats, std_multiplier=2.0, data_path=DATA_PATH)

    mean = age_stats["mean"]
    std = age_stats["std"]

    # Locate the "age" column position in the OHE feature space.
    import numpy as np
    import pandas as pd

    df = pd.read_csv(
        DATA_PATH,
        header=None,
        names=inject_drift.COLUMN_NAMES,
        skipinitialspace=True,
    )
    string_columns = df.select_dtypes(include="object").columns
    for col in string_columns:
        df[col] = df[col].astype(str).str.strip()
    df = df.replace("?", np.nan)
    df = df.dropna()
    X = df.drop(columns=["income"])
    X_ohe = pd.get_dummies(X)
    age_index = list(X_ohe.columns).index("age")

    age_value = drifted_row[age_index]

    assert age_value > mean + 1.5 * std
    assert age_value == pytest.approx(38.6 + 2.0 * 13.6, abs=2.0)


def test_drifted_row_has_correct_feature_count():
    feature_stats = inject_drift.compute_feature_stats(DATA_PATH)
    drifted_row = inject_drift.create_drifted_row(feature_stats, std_multiplier=2.0, data_path=DATA_PATH)

    import numpy as np
    import pandas as pd

    df = pd.read_csv(
        DATA_PATH,
        header=None,
        names=inject_drift.COLUMN_NAMES,
        skipinitialspace=True,
    )
    string_columns = df.select_dtypes(include="object").columns
    for col in string_columns:
        df[col] = df[col].astype(str).str.strip()
    df = df.replace("?", np.nan)
    df = df.dropna()
    X = df.drop(columns=["income"])
    X_ohe = pd.get_dummies(X)

    assert drifted_row.shape == (X_ohe.shape[1],)

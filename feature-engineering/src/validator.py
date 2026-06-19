"""Schema and output validation for the feature-engineering pipeline.

validate_input runs before fitting/transforming — it catches schema drift
(renamed or missing columns) before bad data reaches the pipeline.

validate_output runs after transformation — it catches imputation bugs that
would otherwise silently propagate NaN into a downstream model.
"""

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = [
    "age", "workclass", "fnlwgt", "education", "education-num",
    "marital-status", "occupation", "relationship", "race", "sex",
    "capital-gain", "capital-loss", "hours-per-week", "native-country",
]


def validate_input(df: pd.DataFrame, expected_columns: list[str] | None = None) -> None:
    """Validate that df has all expected columns and at least one row.

    Does not modify df. Raises ValueError on schema violations.
    """
    if expected_columns is None:
        expected_columns = REQUIRED_COLUMNS

    missing_cols = [col for col in expected_columns if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing columns: {missing_cols}")

    if len(df) == 0:
        raise ValueError("DataFrame is empty")


def validate_output(arr: np.ndarray) -> None:
    """Validate the transformed output array.

    Checks shape (2D, non-zero rows) and absence of NaN values. Does not
    check dtype — float32 and float64 are both valid.
    """
    if arr.ndim != 2:
        raise ValueError("Output must be 2D array")

    if arr.shape[0] == 0:
        raise ValueError("Output has zero rows")

    if np.isnan(arr).any():
        raise ValueError("Output contains NaN values after transformation")

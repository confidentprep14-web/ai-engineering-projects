"""Load the UCI Adult Income dataset into a pandas DataFrame."""
import os

import numpy as np
import pandas as pd

COLUMN_NAMES = [
    "age", "workclass", "fnlwgt", "education", "education-num",
    "marital-status", "occupation", "relationship", "race", "sex",
    "capital-gain", "capital-loss", "hours-per-week", "native-country", "income",
]

NUMERIC_COLUMNS = [
    "age", "fnlwgt", "education-num", "capital-gain",
    "capital-loss", "hours-per-week",
]

CATEGORICAL_COLUMNS = [
    "workclass", "education", "marital-status", "occupation",
    "relationship", "race", "sex", "native-country", "income",
]


def load_adult_dataset(path: str) -> pd.DataFrame:
    """Load the UCI Adult Income CSV (no header row) into a labeled DataFrame.

    - Assigns COLUMN_NAMES as the header.
    - Strips leading/trailing whitespace from all string-valued cells.
    - Replaces '?' (after stripping) with NaN in all string columns.
    - Does NOT drop rows with missing values.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Dataset not found at: {path}")

    df = pd.read_csv(path, header=None, skipinitialspace=True)

    if df.shape[1] < 15:
        raise ValueError(f"Expected 15 columns, got {df.shape[1]}")

    df.columns = COLUMN_NAMES

    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].str.strip()
            df[col] = df[col].replace("?", np.nan)

    return df

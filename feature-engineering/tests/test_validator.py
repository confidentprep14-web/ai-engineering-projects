"""Tests for src/validator.py — input schema and output validation."""

import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from validator import validate_input, validate_output


def test_validate_input_raises_on_missing_column():
    df = pd.DataFrame({
        "workclass": ["Private"],
        "fnlwgt": [100],
        "education": ["Bachelors"],
        "education-num": [13],
        "marital-status": ["Never-married"],
        "occupation": ["Tech-support"],
        "relationship": ["Not-in-family"],
        "race": ["White"],
        "sex": ["Male"],
        "capital-gain": [0],
        "capital-loss": [0],
        "hours-per-week": [40],
        "native-country": ["United-States"],
        # "age" is intentionally missing
    })

    with pytest.raises(ValueError) as exc_info:
        validate_input(df)

    assert "age" in str(exc_info.value)


def test_validate_output_raises_on_nan():
    arr = np.array([[1.0, 2.0, 3.0], [4.0, np.nan, 6.0]])

    with pytest.raises(ValueError) as exc_info:
        validate_output(arr)

    assert "NaN" in str(exc_info.value)

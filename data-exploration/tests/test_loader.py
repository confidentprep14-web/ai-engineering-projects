"""Tests for src/loader.py."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from loader import COLUMN_NAMES, load_adult_dataset  # noqa: E402

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _write_csv(tmp_path, filename, rows):
    """Write rows (list of comma-joined strings) to a CSV file and return its path."""
    path = os.path.join(tmp_path, filename)
    with open(path, "w") as f:
        f.write("\n".join(rows) + "\n")
    return path


def _sample_row(**overrides):
    """Build one valid 15-column adult.data row, with optional field overrides."""
    fields = {
        "age": "39",
        "workclass": "State-gov",
        "fnlwgt": "77516",
        "education": "Bachelors",
        "education-num": "13",
        "marital-status": "Never-married",
        "occupation": "Adm-clerical",
        "relationship": "Not-in-family",
        "race": "White",
        "sex": "Male",
        "capital-gain": "2174",
        "capital-loss": "0",
        "hours-per-week": "40",
        "native-country": "United-States",
        "income": "<=50K",
    }
    fields.update(overrides)
    return ",".join(fields[col] for col in COLUMN_NAMES)


def test_load_handles_question_mark_as_nan(tmp_path):
    rows = [
        _sample_row(),
        _sample_row(workclass=" ?"),
    ]
    path = _write_csv(tmp_path, "sample.csv", rows)

    df = load_adult_dataset(path)

    assert df["workclass"].isna().any()
    for col in df.columns:
        if df[col].dtype == object:
            assert not (df[col] == "?").any()


def test_load_assigns_correct_column_names(tmp_path):
    rows = [_sample_row(), _sample_row(age="50")]
    path = _write_csv(tmp_path, "sample.csv", rows)

    df = load_adult_dataset(path)

    assert list(df.columns) == COLUMN_NAMES


def test_load_strips_whitespace(tmp_path):
    rows = [_sample_row(income=" >50K ")]
    path = _write_csv(tmp_path, "sample.csv", rows)

    df = load_adult_dataset(path)

    assert df.loc[0, "income"] == ">50K"


def test_load_raises_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_adult_dataset("/nonexistent/path/does-not-exist.data")


def test_load_raises_value_error_on_wrong_column_count(tmp_path):
    path = os.path.join(tmp_path, "bad.csv")
    with open(path, "w") as f:
        f.write("1,2,3\n4,5,6\n")

    with pytest.raises(ValueError):
        load_adult_dataset(path)

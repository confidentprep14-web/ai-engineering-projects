"""Tests for src/train.py — the single training script that runs both locally and on SageMaker."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xgboost as xgb

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
DATA_DIR = REPO_ROOT / "data"

sys.path.insert(0, str(SRC_DIR))

import train  # noqa: E402


def test_train_produces_accuracy_above_threshold(tmp_path):
    """Run train.main() with the actual adult.data in a temp dir; accuracy must be > 0.80."""
    adult_data = DATA_DIR / "adult.data"
    assert adult_data.exists(), f"Expected dataset at {adult_data} — run the curl download step first"

    model_dir = tmp_path / "model"
    model_dir.mkdir()

    result = train.main(
        [
            "--data-dir",
            str(DATA_DIR),
            "--model-dir",
            str(model_dir),
        ]
    )

    assert result["accuracy"] > 0.80
    assert (model_dir / "model.xgb").exists()


def test_train_saves_model_file(tmp_path):
    """train.save_model(mock_model, tmp_path) with a tiny fitted XGBClassifier writes a non-empty file."""
    X = pd.DataFrame(np.random.rand(20, 4), columns=["a", "b", "c", "d"])
    y = pd.Series([0, 1] * 10)

    model = xgb.XGBClassifier(n_estimators=2, max_depth=2, use_label_encoder=False, eval_metric="logloss")
    model.fit(X, y)

    saved_path = train.save_model(model, str(tmp_path))

    saved_file = Path(saved_path)
    assert saved_file.exists()
    assert saved_file.stat().st_size > 0
    assert saved_file == tmp_path / "model.xgb"


def test_local_and_sagemaker_use_same_entrypoint():
    """src/train.py must exist and define main() — the same entrypoint sagemaker_launch.py relies on."""
    train_py = SRC_DIR / "train.py"
    assert train_py.exists()
    contents = train_py.read_text()
    assert "def main(" in contents


def test_load_data_handles_question_mark(tmp_path):
    """A '?' value in workclass must become NaN and be dropped — never survive as a literal string."""
    row_with_question_mark = (
        "39, ?, 77516, Bachelors, 13, Never-married, Adm-clerical, Not-in-family, "
        "White, Male, 2174, 0, 40, United-States, <=50K\n"
    )
    row_clean = (
        "50, Self-emp-not-inc, 83311, Bachelors, 13, Married-civ-spouse, Exec-managerial, "
        "Husband, White, Male, 0, 0, 13, United-States, <=50K\n"
    )

    data_file = tmp_path / "adult.data"
    data_file.write_text(row_with_question_mark + row_clean)

    X, y = train.load_data(str(tmp_path))

    assert not (X.astype(str) == "?").any().any()
    assert not (X.astype(str) == " ?").any().any()

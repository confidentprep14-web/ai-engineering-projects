"""Tests for src/train_variant.py — model file is saved and AUC is reasonable."""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
DATA_DIR = REPO_ROOT / "data"

sys.path.insert(0, str(SRC_DIR))

import train_variant  # noqa: E402


def test_model_file_is_saved(tmp_path):
    metadata = train_variant.main(
        [
            "--max-depth",
            "3",
            "--learning-rate",
            "0.1",
            "--data",
            str(DATA_DIR / "adult.data"),
            "--models-dir",
            str(tmp_path),
        ]
    )

    model_path = tmp_path / metadata["run_id"] / "model.xgb"
    assert model_path.exists()


def test_val_auc_is_reasonable(tmp_path):
    metadata = train_variant.main(
        [
            "--max-depth",
            "3",
            "--learning-rate",
            "0.1",
            "--data",
            str(DATA_DIR / "adult.data"),
            "--models-dir",
            str(tmp_path),
        ]
    )

    metadata_path = tmp_path / metadata["run_id"] / "metadata.json"
    with open(metadata_path) as f:
        loaded = json.load(f)

    assert loaded["metrics"]["val_auc"] > 0.80

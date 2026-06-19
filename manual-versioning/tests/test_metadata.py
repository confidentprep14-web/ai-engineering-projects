"""Tests for metadata.json schema, run uniqueness, and compare.py correctness."""

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
DATA_DIR = REPO_ROOT / "data"

sys.path.insert(0, str(SRC_DIR))

import compare  # noqa: E402
import train_all  # noqa: E402
import train_variant  # noqa: E402


class _MockModel:
    """Stand-in for an XGBClassifier — only needs save_model() for save_run()."""

    def save_model(self, path):
        Path(path).write_text("mock model bytes")


def test_metadata_json_has_all_required_keys(tmp_path):
    hyperparams = {"max_depth": 3, "learning_rate": 0.1, "n_estimators": 100}
    metrics = {"val_auc": 0.8762, "train_time_seconds": 4.21}

    train_variant.save_run(_MockModel(), "run_test", hyperparams, metrics, str(tmp_path))

    metadata_path = tmp_path / "run_test" / "metadata.json"
    assert metadata_path.exists()

    with open(metadata_path) as f:
        metadata = json.load(f)

    for key in ("run_id", "hyperparams", "metrics", "model_path", "created_at"):
        assert key in metadata

    assert "val_auc" in metadata["metrics"]
    assert "train_time_seconds" in metadata["metrics"]

    for key in ("max_depth", "learning_rate", "n_estimators"):
        assert key in metadata["hyperparams"]


def test_compare_finds_all_three_runs_after_train_all(tmp_path):
    models_dir = tmp_path / "models"

    train_all.main(["--data", str(DATA_DIR / "adult.data"), "--models-dir", str(models_dir)])

    runs = compare.find_all_runs(str(models_dir))
    assert len(runs) == 3


def test_best_run_identified_correctly():
    runs = [
        {"run_id": "run_a", "metrics": {"val_auc": 0.85}},
        {"run_id": "run_b", "metrics": {"val_auc": 0.90}},
        {"run_id": "run_c", "metrics": {"val_auc": 0.87}},
    ]

    best = compare.identify_best_run(runs)
    assert best["metrics"]["val_auc"] == 0.90


def test_run_id_is_unique_per_run():
    first = train_variant.generate_run_id()
    time.sleep(1)
    second = train_variant.generate_run_id()

    assert first != second

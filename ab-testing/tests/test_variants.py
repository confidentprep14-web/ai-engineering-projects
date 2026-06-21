import os
import sys
from unittest.mock import patch

import numpy as np
import pytest
from xgboost import XGBClassifier

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import prepare_variants  # noqa: E402


def test_prepare_variants_creates_distinct_s3_uris(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("S3_BUCKET", "mock-bucket")
    monkeypatch.setenv("MLFLOW_MODEL_NAME", "adult-income-xgboost")
    monkeypatch.setenv("CHALLENGER_MAX_DEPTH", "2")
    monkeypatch.setenv("CHALLENGER_LEARNING_RATE", "0.1")
    monkeypatch.setenv("CHALLENGER_N_ESTIMATORS", "3")

    rng = np.random.RandomState(0)
    X = rng.rand(40, 4)
    y = (X[:, 0] > 0.5).astype(int)
    tiny_model = XGBClassifier(n_estimators=3, max_depth=2)
    tiny_model.fit(X, y)

    data_path = tmp_path / "adult.data"
    data_path.write_text("")

    recorded_variant_names = []

    def fake_package_and_upload(model, variant_name, bucket):
        recorded_variant_names.append(variant_name)
        return f"s3://{bucket}/p3-08/{variant_name}/model.tar.gz"

    with patch("prepare_variants.mlflow.set_tracking_uri"), \
         patch("prepare_variants.load_current_model", return_value=tiny_model), \
         patch("prepare_variants.train_challenger", return_value=(tiny_model, 0.91)), \
         patch("prepare_variants.package_and_upload", side_effect=fake_package_and_upload), \
         patch("sys.argv", ["prepare_variants.py"]):
        prepare_variants.main()

    assert recorded_variant_names == ["current", "challenger"]
    assert len(set(recorded_variant_names)) == 2

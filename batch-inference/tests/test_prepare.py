import os
import sys
import tarfile

import numpy as np
from xgboost import XGBClassifier

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import prepare_model  # noqa: E402


def test_create_model_tar_has_correct_structure(tmp_path):
    rng = np.random.RandomState(0)
    X = rng.rand(20, 4)
    y = (X[:, 0] > 0.5).astype(int)
    model = XGBClassifier(n_estimators=3, max_depth=2)
    model.fit(X, y)

    tar_path = prepare_model.create_model_tar(model, str(tmp_path / "model.tar.gz"))

    with tarfile.open(tar_path, "r:gz") as tar:
        member_names = tar.getnames()

    assert "model.xgb" in member_names
    assert "inference.py" in member_names

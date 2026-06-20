import os
import sys

import numpy as np
from xgboost import XGBClassifier

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import inference  # noqa: E402


def _make_tiny_model() -> XGBClassifier:
    rng = np.random.RandomState(0)
    X = rng.rand(20, 4)
    y = (X[:, 0] > 0.5).astype(int)
    model = XGBClassifier(n_estimators=3, max_depth=2)
    model.fit(X, y)
    return model


def test_model_fn_loads_model_correctly(tmp_path):
    model = _make_tiny_model()
    model.save_model(str(tmp_path / "model.xgb"))

    loaded = inference.model_fn(str(tmp_path))

    assert isinstance(loaded, XGBClassifier)
    # NOTE: spec says "assert n_estimators > 0", but XGBClassifier.load_model()
    # only restores the underlying Booster -- it does not re-populate sklearn
    # constructor params like n_estimators, which stay None after a fresh
    # XGBClassifier() + load_model() (confirmed directly: before save,
    # model.n_estimators == 3; after load_model() into a new instance,
    # loaded.n_estimators is None). The booster's round count is the
    # correct signal that a real, fitted model was loaded.
    assert loaded.get_booster().num_boosted_rounds() > 0


def test_predict_fn_returns_probabilities():
    model = _make_tiny_model()
    rng = np.random.RandomState(1)
    arr = rng.rand(5, 4)

    output = inference.predict_fn(arr, model)

    assert output.shape == (5,)
    assert np.all(output >= 0.0) and np.all(output <= 1.0)

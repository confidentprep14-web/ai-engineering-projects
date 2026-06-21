import os
import sys

import numpy as np
from xgboost import XGBClassifier

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import inference  # noqa: E402


def _make_tiny_model() -> XGBClassifier:
    rng = np.random.RandomState(0)
    X = rng.rand(10, 10)
    y = (X[:, 0] > 0.5).astype(int)
    model = XGBClassifier(n_estimators=3, max_depth=2)
    model.fit(X, y)
    return model


def test_predict_fn_returns_probabilities_as_list():
    model = _make_tiny_model()
    rng = np.random.RandomState(1)
    arr = rng.rand(5, 10)

    result = inference.predict_fn(arr, model)

    assert isinstance(result, list)
    assert len(result) == 5
    assert all(0.0 <= v <= 1.0 for v in result)


def test_predict_fn_reshapes_1d_input():
    model = _make_tiny_model()
    arr = np.random.RandomState(2).rand(10)

    result = inference.predict_fn(arr, model)

    assert len(result) == 1


def test_output_fn_csv_format():
    result = inference.output_fn([0.82, 0.31], "text/csv")

    assert result[0] == "0.82,0.31"
    assert result[1] == "text/csv"

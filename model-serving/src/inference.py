"""SageMaker inference handlers for the Adult Income XGBoost model.

This module is packaged inside model.tar.gz (at the archive root, alongside
model.xgb) and is loaded by the SageMaker XGBoost framework container via the
SAGEMAKER_PROGRAM environment variable. SageMaker imports these four
functions and calls them in order for every real-time invocation:

    model = model_fn(model_dir)
    data = input_fn(request_body, content_type)
    prediction = predict_fn(data, model)
    response = output_fn(prediction, accept)
"""
import json
from io import StringIO

import numpy as np
import pandas as pd
import xgboost as xgb


def model_fn(model_dir: str) -> xgb.XGBClassifier:
    """Load the model artifact written by deploy.py's create_model_tar step.

    SageMaker extracts model.tar.gz into model_dir before calling this, so
    the file always lands at "{model_dir}/model.xgb".
    """
    model = xgb.XGBClassifier()
    model.load_model(f"{model_dir}/model.xgb")
    return model


def input_fn(request_body, content_type: str) -> np.ndarray:
    """Parse the request body into a 2D float64 numpy array.

    Only text/csv is supported -- that's what benchmark.py sends and what the
    endpoint is configured to accept.
    """
    if content_type != "text/csv":
        raise ValueError(f"Unsupported content type: {content_type}")

    if isinstance(request_body, bytes):
        request_body = request_body.decode("utf-8")

    df = pd.read_csv(StringIO(request_body), header=None)
    return df.values.astype(np.float64)


def predict_fn(input_data: np.ndarray, model: xgb.XGBClassifier) -> list:
    """Return the positive-class probability for each row, as a list of floats.

    Edge case: a single 1D row (shape (n_features,)) is reshaped to a single
    row, 2D array (1, n_features) before calling predict_proba -- XGBoost
    requires 2D input.
    """
    if input_data.ndim == 1:
        input_data = input_data.reshape(1, -1)

    return model.predict_proba(input_data)[:, 1].tolist()


def output_fn(prediction: list, accept: str):
    """Serialize predictions as CSV (default) or JSON, depending on `accept`."""
    if accept == "application/json":
        return json.dumps({"predictions": prediction}), "application/json"

    return ",".join(str(p) for p in prediction), "text/csv"

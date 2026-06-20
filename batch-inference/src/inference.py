"""SageMaker inference handlers for the Adult Income XGBoost model.

This module is packaged inside model.tar.gz (at the archive root, alongside
model.xgb) and is loaded by the SageMaker XGBoost framework container via the
SAGEMAKER_PROGRAM environment variable. SageMaker imports these four
functions and calls them in order for every request (or every CSV line, when
the Batch Transform job is configured with split_type="Line"):

    model = model_fn(model_dir)
    data = input_fn(request_body, content_type)
    prediction = predict_fn(data, model)
    response = output_fn(prediction, accept)
"""
from io import StringIO

import numpy as np
import pandas as pd
import xgboost as xgb


def model_fn(model_dir: str) -> xgb.XGBClassifier:
    """Load the model artifact written by create_model_tar.

    SageMaker extracts model.tar.gz into model_dir before calling this, so
    the file always lands at "{model_dir}/model.xgb".
    """
    model = xgb.XGBClassifier()
    model.load_model(f"{model_dir}/model.xgb")
    return model


def input_fn(request_body: str, content_type: str) -> np.ndarray:
    """Parse the request body into a 2D float64 numpy array.

    Only text/csv is supported -- that's what prepare_test_data writes and
    what the Transformer job is configured to send (content_type="text/csv").
    """
    if content_type != "text/csv":
        raise ValueError(f"Unsupported content type: {content_type}")

    df = pd.read_csv(StringIO(request_body), header=None)
    return df.values.astype(np.float64)


def predict_fn(input_data: np.ndarray, model: xgb.XGBClassifier) -> np.ndarray:
    """Return the positive-class probability for each row."""
    return model.predict_proba(input_data)[:, 1]


def output_fn(prediction: np.ndarray, accept: str) -> str:
    """Serialize predictions as newline-joined CSV values."""
    return "\n".join(str(value) for value in prediction)

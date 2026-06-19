"""Reusable sklearn preprocessing pipeline for the UCI Adult Income dataset.

Numeric columns: median imputation -> StandardScaler.
Categorical columns: most_frequent imputation -> OneHotEncoder (handle_unknown=ignore).
Both branches are combined with a ColumnTransformer wrapped in a top-level
Pipeline. There is no estimator here — this is preprocessing only.
"""

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

NUMERIC_FEATURES = [
    "age", "fnlwgt", "education-num",
    "capital-gain", "capital-loss", "hours-per-week",
]
CATEGORICAL_FEATURES = [
    "workclass", "education", "marital-status",
    "occupation", "relationship", "race",
    "sex", "native-country",
]
TARGET_COLUMN = "income"


def build_pipeline() -> Pipeline:
    """Construct the (unfitted) preprocessing pipeline.

    Returns a top-level Pipeline whose single named step "preprocessor" is a
    ColumnTransformer with a numeric branch (median impute -> scale) and a
    categorical branch (most_frequent impute -> one-hot encode).
    """
    numeric_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])

    categorical_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])

    preprocessor = ColumnTransformer([
        ("numeric", numeric_pipeline, NUMERIC_FEATURES),
        ("categorical", categorical_pipeline, CATEGORICAL_FEATURES),
    ])

    return Pipeline([("preprocessor", preprocessor)])


def fit_and_transform(pipeline: Pipeline, X: pd.DataFrame) -> np.ndarray:
    """Fit the pipeline on X and return the transformed array.

    Mutates `pipeline` only via the side effects of `fit_transform` itself
    (i.e. it becomes fitted) — no extra state is added on top.
    """
    return pipeline.fit_transform(X)


def transform(pipeline: Pipeline, X: pd.DataFrame) -> np.ndarray:
    """Transform X using an already-fitted pipeline.

    Raises sklearn.exceptions.NotFittedError (propagated naturally) if the
    pipeline has not been fitted yet.
    """
    return pipeline.transform(X)


def get_feature_names(pipeline: Pipeline) -> list[str]:
    """Return the flat list of output feature names from the fitted pipeline."""
    return list(pipeline.named_steps["preprocessor"].get_feature_names_out())

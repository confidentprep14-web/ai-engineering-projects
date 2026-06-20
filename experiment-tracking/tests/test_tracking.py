"""Tests for MLflow run tracking — exercised against a temp file-store
tracking URI, not the live server.
"""
import os
import sys
import uuid

import mlflow
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import select_best  # noqa: E402
import train_with_mlflow  # noqa: E402

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "adult.data")


@pytest.fixture()
def temp_tracking_uri(tmp_path):
    uri = f"file://{tmp_path}/mlruns_test"
    mlflow.set_tracking_uri(uri)
    yield uri


def test_mlflow_run_created_with_correct_experiment(temp_tracking_uri):
    X_train, X_test, y_train, y_test = train_with_mlflow.load_and_split(DATA_PATH)

    params = {"max_depth": 3, "learning_rate": 0.1, "n_estimators": 10}
    run_id = train_with_mlflow.train_and_log(
        X_train, X_test, y_train, y_test, params, experiment_name="test-experiment"
    )

    assert isinstance(run_id, str)
    assert len(run_id) > 0
    assert mlflow.get_experiment_by_name("test-experiment") is not None


def test_best_model_selection_picks_highest_auc(temp_tracking_uri):
    experiment_name = f"test-experiment-{uuid.uuid4().hex[:8]}"
    mlflow.set_experiment(experiment_name)

    for auc in (0.85, 0.91, 0.87):
        with mlflow.start_run():
            mlflow.log_metric("val_auc", auc)

    best_run_df = select_best.find_best_run(experiment_name)

    assert best_run_df.iloc[0]["metrics.val_auc"] == 0.91

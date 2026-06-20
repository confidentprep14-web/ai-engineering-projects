"""Tests for the Model Registry alias workflow — exercised against a temp
file-store tracking URI, not the live server.
"""
import os
import sys
import uuid

import mlflow
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import load_and_infer  # noqa: E402
import select_best  # noqa: E402
import sweep  # noqa: E402
from mlflow import MlflowClient  # noqa: E402

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "adult.data")


@pytest.fixture()
def temp_tracking_uri(tmp_path):
    uri = f"file://{tmp_path}/mlruns_test"
    mlflow.set_tracking_uri(uri)
    yield uri


def test_production_alias_set_after_select_best(temp_tracking_uri):
    experiment_name = f"test-experiment-{uuid.uuid4().hex[:8]}"
    model_name = f"test-model-{uuid.uuid4().hex[:8]}"

    sweep.run_sweep(sweep.SWEEP_CONFIGS[:2], DATA_PATH, experiment_name)

    best_run_df = select_best.find_best_run(experiment_name)
    best_run = best_run_df.iloc[0]
    select_best.register_best_model(best_run, model_name=model_name, alias="production")

    client = MlflowClient()
    model_version = client.get_model_version_by_alias(model_name, "production")

    assert model_version is not None


def test_load_and_infer_produces_predictions_without_error(temp_tracking_uri):
    experiment_name = f"test-experiment-{uuid.uuid4().hex[:8]}"
    model_name = f"test-model-{uuid.uuid4().hex[:8]}"

    sweep.run_sweep(sweep.SWEEP_CONFIGS[:2], DATA_PATH, experiment_name)
    best_run_df = select_best.find_best_run(experiment_name)
    best_run = best_run_df.iloc[0]
    select_best.register_best_model(best_run, model_name=model_name, alias="production")

    model = load_and_infer.load_production_model(model_name, "production")
    result = load_and_infer.run_inference(model, DATA_PATH, n_samples=3)

    assert len(result) == 3
    assert "prediction" in result.columns

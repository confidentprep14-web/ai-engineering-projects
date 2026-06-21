"""Promote the A/B test winner to the MLflow registry: if the challenger
won, register its model and move the "production" alias to it; if the
current model won, do nothing.
"""
import argparse
import json
import os

import mlflow
import mlflow.xgboost
from dotenv import load_dotenv
from mlflow import MlflowClient
from xgboost import XGBClassifier

load_dotenv()


def promote_to_production(winner: str, model_name: str, challenger_model: XGBClassifier = None) -> None:
    """If `winner == "challenger"`, log it as a new MLflow run, register it,
    and set the "production" alias to the new version. If `winner ==
    "current"`, leave the registry untouched.
    """
    if winner == "challenger":
        if challenger_model is None:
            raise ValueError("challenger_model is required to promote the challenger")

        with mlflow.start_run(run_name="p3-08-challenger-promoted") as run:
            mlflow.xgboost.log_model(challenger_model, artifact_path="model")
            model_uri = f"runs:/{run.info.run_id}/model"

        model_version = mlflow.register_model(model_uri, model_name)

        client = MlflowClient()
        client.set_registered_model_alias(model_name, "production", model_version.version)

        print("Challenger promoted to production. Registry updated.")
    else:
        print("Current model retained. No registry change.")


def _load_challenger_model() -> XGBClassifier:
    """Retrain the challenger from scratch using the same hyperparams and
    data prepare_variants.py used, so promote_winner.py can be run as a
    standalone step without holding the model object in memory.
    """
    import prepare_variants

    hyperparams = {
        "max_depth": int(os.getenv("CHALLENGER_MAX_DEPTH", "7")),
        "learning_rate": float(os.getenv("CHALLENGER_LEARNING_RATE", "0.05")),
        "n_estimators": int(os.getenv("CHALLENGER_N_ESTIMATORS", "200")),
    }
    model, _ = prepare_variants.train_challenger("data/adult.data", hyperparams)
    return model


def main():
    parser = argparse.ArgumentParser(description="Promote the A/B test winner to the MLflow registry")
    parser.add_argument("--winner", type=str, choices=["current", "challenger"], default=None)
    args = parser.parse_args()

    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    model_name = os.getenv("MLFLOW_MODEL_NAME", "adult-income-xgboost")

    winner = args.winner
    if winner is None:
        if not os.path.exists("output/ab_decision.json"):
            raise FileNotFoundError(
                "No --winner given and output/ab_decision.json not found -- "
                "run python src/evaluate_winner.py first."
            )
        with open("output/ab_decision.json") as f:
            decision = json.load(f)
        winner = decision["winner"]

    challenger_model = _load_challenger_model() if winner == "challenger" else None
    promote_to_production(winner, model_name, challenger_model)


if __name__ == "__main__":
    main()

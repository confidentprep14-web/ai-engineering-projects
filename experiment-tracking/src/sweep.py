"""Run a 5-configuration hyperparameter sweep, each as a separate MLflow run."""
import os

from dotenv import load_dotenv

import train_with_mlflow

load_dotenv()

SWEEP_CONFIGS = [
    {"max_depth": 3, "learning_rate": 0.1, "n_estimators": 100},
    {"max_depth": 5, "learning_rate": 0.1, "n_estimators": 100},
    {"max_depth": 7, "learning_rate": 0.1, "n_estimators": 100},
    {"max_depth": 5, "learning_rate": 0.05, "n_estimators": 200},
    {"max_depth": 5, "learning_rate": 0.01, "n_estimators": 200},
]


def run_sweep(configs: list, data_path: str, experiment_name: str) -> list:
    """Run each config as a separate MLflow run. Returns list of run_ids."""
    X_train, X_test, y_train, y_test = train_with_mlflow.load_and_split(data_path)

    run_ids = []
    for i, config in enumerate(configs):
        print(f"Running sweep {i + 1}/{len(configs)}: {config}")
        run_id = train_with_mlflow.train_and_log(
            X_train,
            X_test,
            y_train,
            y_test,
            config,
            experiment_name,
            run_name=f"sweep-{i + 1}",
        )
        run_ids.append(run_id)
    return run_ids


def main():
    experiment_name = os.getenv("MLFLOW_EXPERIMENT_NAME", "adult-income-sweep")
    data_path = os.getenv("LOCAL_DATA_DIR", "data/") + "adult.data"

    run_ids = run_sweep(SWEEP_CONFIGS, data_path, experiment_name)

    print(f'Sweep complete. {len(run_ids)} runs in experiment "{experiment_name}"')
    print("View at: http://localhost:5000")


if __name__ == "__main__":
    main()

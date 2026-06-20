"""Single MLflow-instrumented training run on the UCI Adult Income dataset.

Logs hyperparameters, per-round validation logloss, final metrics, and the
trained XGBoost model to MLflow.
"""
import argparse
import os

import mlflow
import mlflow.xgboost
import pandas as pd
from dotenv import load_dotenv
from sklearn.metrics import accuracy_score, roc_auc_score
from xgboost import XGBClassifier

load_dotenv()

COLUMN_NAMES = [
    "age", "workclass", "fnlwgt", "education", "education_num",
    "marital_status", "occupation", "relationship", "race", "sex",
    "capital_gain", "capital_loss", "hours_per_week", "native_country",
    "income",
]


def load_and_split(data_path: str) -> tuple:
    """Load the UCI Adult dataset and split into train/test sets.

    Returns (X_train, X_test, y_train, y_test), an 80/20 split with
    random_state=42.
    """
    from sklearn.model_selection import train_test_split

    df = pd.read_csv(
        data_path,
        names=COLUMN_NAMES,
        sep=r",\s*",
        engine="python",
        na_values="?",
    )
    df = df.apply(lambda col: col.str.strip() if col.dtype == "object" else col)
    df = df.dropna()

    y = df["income"].apply(lambda v: 1 if v.strip().rstrip(".") == ">50K" else 0)
    X = df.drop(columns=["income"])
    X = pd.get_dummies(X)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    return X_train, X_test, y_train, y_test


def train_and_log(
    X_train,
    X_test,
    y_train,
    y_test,
    params: dict,
    experiment_name: str,
    run_name: str | None = None,
) -> str:
    """Train an XGBoost model and log params/metrics/model to MLflow.

    Returns the MLflow run_id.
    """
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    mlflow.set_experiment(experiment_name)

    with mlflow.start_run(run_name=run_name) as run:
        mlflow.log_param("max_depth", params["max_depth"])
        mlflow.log_param("learning_rate", params["learning_rate"])
        mlflow.log_param("n_estimators", params["n_estimators"])

        model = XGBClassifier(eval_metric="logloss", **params)
        model.fit(
            X_train,
            y_train,
            eval_set=[(X_test, y_test)],
            verbose=False,
        )

        results = model.evals_result()
        for i, loss in enumerate(results["validation_0"]["logloss"]):
            mlflow.log_metric("val_logloss", loss, step=i)

        val_auc = roc_auc_score(y_test, model.predict_proba(X_test)[:, 1])
        val_acc = accuracy_score(y_test, model.predict(X_test))
        mlflow.log_metric("val_auc", val_auc)
        mlflow.log_metric("val_accuracy", val_acc)

        mlflow.xgboost.log_model(model, artifact_path="model")

        return run.info.run_id


def main():
    parser = argparse.ArgumentParser(description="Train one XGBoost run with MLflow tracking")
    parser.add_argument("--max-depth", type=int, default=5)
    parser.add_argument("--learning-rate", type=float, default=0.1)
    parser.add_argument("--n-estimators", type=int, default=100)
    parser.add_argument("--data", type=str, default="data/adult.data")
    parser.add_argument(
        "--experiment-name",
        type=str,
        default=os.getenv("MLFLOW_EXPERIMENT_NAME", "adult-income-sweep"),
    )
    parser.add_argument("--run-name", type=str, default=None)
    args = parser.parse_args()

    X_train, X_test, y_train, y_test = load_and_split(args.data)

    params = {
        "max_depth": args.max_depth,
        "learning_rate": args.learning_rate,
        "n_estimators": args.n_estimators,
    }

    try:
        run_id = train_and_log(
            X_train, X_test, y_train, y_test, params, args.experiment_name, args.run_name
        )
    except mlflow.exceptions.MlflowException as e:
        print(f"Is the MLflow server running? Run: python src/start_server.py\n({e})")
        raise

    run_data = mlflow.get_run(run_id).data
    val_auc = run_data.metrics["val_auc"]
    print(f"Run {run_id} complete. val_auc={val_auc:.4f}")


if __name__ == "__main__":
    main()

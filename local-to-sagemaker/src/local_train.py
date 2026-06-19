"""Thin wrapper to invoke train.py locally via subprocess."""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ACCURACY_PATTERN = re.compile(r"ACCURACY:\s*(\d+\.\d+)")


def run_local(data_path: str, model_dir: str, hyperparams: dict) -> dict:
    """Copy data_path into a temp dir, run train.py as a subprocess, return accuracy + model path."""
    print("Training locally...")

    with tempfile.TemporaryDirectory() as tmp_data_dir:
        dest = Path(tmp_data_dir) / Path(data_path).name
        shutil.copy(data_path, dest)

        train_py = Path(__file__).resolve().parent / "train.py"
        cmd = [
            sys.executable,
            str(train_py),
            "--data-dir",
            tmp_data_dir,
            "--model-dir",
            model_dir,
        ]
        if "max_depth" in hyperparams:
            cmd += ["--max-depth", str(hyperparams["max_depth"])]
        if "learning_rate" in hyperparams:
            cmd += ["--learning-rate", str(hyperparams["learning_rate"])]
        if "n_estimators" in hyperparams:
            cmd += ["--n-estimators", str(hyperparams["n_estimators"])]

        completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
        stdout = completed.stdout
        print(stdout)

        match = ACCURACY_PATTERN.search(stdout)
        if match is None:
            raise RuntimeError(
                f"Could not find ACCURACY line in train.py output:\n{stdout}\n{completed.stderr}"
            )
        accuracy = float(match.group(1))

    model_path = str(Path(model_dir) / "model.xgb")
    if not Path(model_path).exists():
        print(f"ERROR: expected model file not found at {model_path}")
    else:
        print(f"Model saved to {model_path}")

    return {"accuracy": accuracy, "model_path": model_path}


def main() -> None:
    parser = argparse.ArgumentParser(description="Train locally by invoking train.py as a subprocess")
    parser.add_argument("--data", required=True, help="Path to adult.data")
    parser.add_argument("--model-dir", default="models")
    parser.add_argument("--max-depth", type=int, default=5)
    parser.add_argument("--learning-rate", type=float, default=0.1)
    parser.add_argument("--n-estimators", type=int, default=100)
    args = parser.parse_args()

    hyperparams = {
        "max_depth": args.max_depth,
        "learning_rate": args.learning_rate,
        "n_estimators": args.n_estimators,
    }

    run_local(args.data, args.model_dir, hyperparams)


if __name__ == "__main__":
    main()

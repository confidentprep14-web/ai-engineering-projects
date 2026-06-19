"""Train 3 hardcoded XGBoost variants sequentially, then print the comparison table.

Each variant is launched as a subprocess (not an in-process function call) so
that train_variant.main() picks up a fresh wall-clock timestamp for its run_id.
We sleep 2 seconds between runs to guarantee the timestamps differ, since
generate_run_id() only has second-level precision.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

import compare

VARIANTS = [
    {"max_depth": 3, "learning_rate": 0.1, "n_estimators": 100},
    {"max_depth": 5, "learning_rate": 0.05, "n_estimators": 100},
    {"max_depth": 7, "learning_rate": 0.01, "n_estimators": 200},
]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Train all 3 hardcoded variants")
    parser.add_argument("--data", type=str, default="data/adult.data")
    parser.add_argument("--models-dir", type=str, default="models/")
    args = parser.parse_args(argv)

    train_variant_py = Path(__file__).resolve().parent / "train_variant.py"

    for i, variant in enumerate(VARIANTS):
        cmd = [
            sys.executable,
            str(train_variant_py),
            "--max-depth",
            str(variant["max_depth"]),
            "--learning-rate",
            str(variant["learning_rate"]),
            "--n-estimators",
            str(variant["n_estimators"]),
            "--data",
            args.data,
            "--models-dir",
            args.models_dir,
        ]
        subprocess.run(cmd, check=True)

        if i < len(VARIANTS) - 1:
            time.sleep(2)

    runs = compare.find_all_runs(args.models_dir)
    print(compare.format_comparison_table(runs))


if __name__ == "__main__":
    main()

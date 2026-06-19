"""Scan models/ for run metadata and print a ranked comparison table.

This is the script that replaces "open three JSON files by hand." It is also
exactly the friction that motivates MLflow in the next project: there is no
central index, just a directory scan.
"""

import argparse
import json
import os


def find_all_runs(models_dir: str) -> list[dict]:
    """Scan models_dir for run subdirectories and load their metadata.json.

    Skips any subdirectory that does not contain a metadata.json (a partial
    or interrupted run) and prints a warning instead of failing.
    Returns the list sorted by run_id ascending (chronological).
    """
    runs = []
    if not os.path.isdir(models_dir):
        return runs

    for entry in sorted(os.listdir(models_dir)):
        run_dir = os.path.join(models_dir, entry)
        if not os.path.isdir(run_dir):
            continue

        metadata_path = os.path.join(run_dir, "metadata.json")
        if not os.path.exists(metadata_path):
            print(f"WARNING: skipping '{run_dir}' — no metadata.json found")
            continue

        with open(metadata_path) as f:
            runs.append(json.load(f))

    runs.sort(key=lambda r: r["run_id"])
    return runs


def identify_best_run(runs: list[dict], metric: str = "val_auc") -> dict:
    """Return the run with the highest metrics[metric] value."""
    if not runs:
        raise ValueError("No runs found in models/. Run train_all.py first.")

    return max(runs, key=lambda r: float(r["metrics"][metric]))


def format_comparison_table(runs: list[dict]) -> str:
    """Build a plain-text comparison table, marking the best run with '*'."""
    if not runs:
        return "No runs found in models/. Run train_all.py first."

    best = identify_best_run(runs)

    header = (
        f"{'run_id':<23} | {'max_depth':>9} | {'learning_rate':>13} | "
        f"{'val_auc':>7} | {'train_time_s':>12}"
    )
    separator = "-" * 24 + "|" + "-" * 11 + "|" + "-" * 15 + "|" + "-" * 9 + "|" + "-" * 13

    lines = [header, separator]
    for run in runs:
        run_id = run["run_id"]
        label = f"*{run_id}" if run_id == best["run_id"] else run_id
        hp = run["hyperparams"]
        metrics = run["metrics"]
        lines.append(
            f"{label:<23} | {hp['max_depth']:>9} | {hp['learning_rate']:>13.3f} | "
            f"{float(metrics['val_auc']):>7.4f} | {float(metrics['train_time_seconds']):>12.2f}"
        )

    lines.append("")
    lines.append(f"Best run: {best['run_id']} (val_auc={float(best['metrics']['val_auc']):.4f})")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Compare all manual training runs")
    parser.add_argument("--models-dir", type=str, default="models/")
    parser.add_argument("--sort-by", type=str, default="val_auc")
    args = parser.parse_args(argv)

    runs = find_all_runs(args.models_dir)
    print(format_comparison_table(runs))


if __name__ == "__main__":
    main()

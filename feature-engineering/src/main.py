"""CLI entry point for the feature-engineering pipeline.

Runs identically locally and as a SageMaker Processing Job — it only knows
about --input / --output paths, never about S3 or containers. SageMaker
Processing mounts S3 input/output to local paths and passes those paths as
--input / --output automatically.
"""

import argparse
import os

import numpy as np
import pandas as pd

from pipeline import build_pipeline, fit_and_transform, get_feature_names
from validator import validate_input, validate_output

COLUMN_NAMES = [
    "age", "workclass", "fnlwgt", "education", "education-num",
    "marital-status", "occupation", "relationship", "race", "sex",
    "capital-gain", "capital-loss", "hours-per-week", "native-country", "income",
]


def load_raw(input_path: str) -> tuple[pd.DataFrame, pd.Series]:
    """Load the raw UCI Adult CSV into (X, y).

    Copies the established loading convention used by p3-01/p3-02 (no header
    row, 15 fixed column names, whitespace-stripped strings, "?" -> NaN)
    rather than importing it from another project's folder. X excludes the
    "income" column; y is the income column.
    """
    df = pd.read_csv(input_path, header=None, skipinitialspace=True)

    df.columns = COLUMN_NAMES

    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].str.strip()
            df[col] = df[col].replace("?", np.nan)

    y = df["income"]
    X = df.drop(columns=["income"])

    return X, y


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Preprocess the UCI Adult Income dataset with a reusable sklearn Pipeline"
    )
    parser.add_argument("--input", required=True, help="Path to raw CSV")
    parser.add_argument("--output", required=True, help="Path to write processed CSV")
    parser.add_argument(
        "--save-pipeline", default=None, help="Path to save the fitted joblib pipeline"
    )
    args = parser.parse_args()

    X, y = load_raw(args.input)

    validate_input(X)

    pipeline = build_pipeline()
    processed_arr = fit_and_transform(pipeline, X)

    validate_output(processed_arr)

    feature_names = get_feature_names(pipeline)
    processed_df = pd.DataFrame(processed_arr, columns=feature_names)
    processed_df[y.name] = y.reset_index(drop=True)

    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    processed_df.to_csv(args.output, index=False)

    n_rows, n_cols = processed_arr.shape
    print(f"Processed {n_rows} rows -> {n_cols} features. Saved to {args.output}")
    print(f"NaN cells in output: {int(np.isnan(processed_arr).sum())}")

    if args.save_pipeline:
        import joblib

        joblib.dump(pipeline, args.save_pipeline)
        print(f"Pipeline saved to {args.save_pipeline}")


if __name__ == "__main__":
    main()

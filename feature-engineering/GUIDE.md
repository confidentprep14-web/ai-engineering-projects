# Guide — Feature Engineering

## Why a Pipeline, not manual steps

Without a Pipeline, you must remember to apply the same scaling and encoding at inference time
that you applied at training time. Forget once and your model receives unscaled inputs — it
silently produces wrong predictions. With a fitted Pipeline serialized to joblib, you call
`pipeline.transform(new_data)` at inference and the exact same transformations apply.

## The ColumnTransformer explained

ColumnTransformer applies different transformations to different column subsets and concatenates
the results horizontally. Numeric columns become scaled floats. Categorical columns become
a sparse binary matrix (one column per category value). The total output width is
`len(NUMERIC_FEATURES) + sum(unique_values_per_categorical_column)`.

For UCI Adult, expect roughly 6 numeric + ~100 OHE columns = ~106 features total. Running the
pipeline against the full dataset in this environment produced 105 features (6 numeric + 99 OHE
columns), which lands inside that range.

## handle_unknown="ignore" matters

At inference time your model may see a `native-country` value that was not in training data.
With `handle_unknown="ignore"`, OneHotEncoder outputs a zero vector for that value instead of
raising an exception. This is the correct production behavior.

## Validation before and after

**Before:** catches schema drift — if the incoming data has a renamed column, you fail early
with a clear message rather than propagating wrong data into the model.

**After:** catches imputation bugs — if your imputer silently failed to fill NaN (e.g., because
the column dtype was wrong), the post-transform check will catch it.

## SageMaker Processing vs local

SageMaker Processing mounts your input from S3 at `/opt/ml/processing/input/` and collects
your output from `/opt/ml/processing/output/`. Your `main.py` uses `--input` and `--output`
arguments — the SKLearnProcessor passes the mounted paths automatically. The script does not
need to know it is running in a container.

## Interview framing

"I build preprocessing as a serialized sklearn Pipeline so the same transformations apply
identically at training and inference time — no manual step synchronization, no silent
preprocessing drift between training and production."

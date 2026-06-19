# Guide — Manual Versioning

## The problem you are about to feel

After running `train_all.py`, open `models/`. You have 3 directories with timestamps you
need to decode. If you want to know which used max_depth=5, you open 3 JSON files. If you
ran an extra experiment by hand, it is in a fourth directory. If a colleague ran experiments
on their machine, their folder is not here at all.

This friction is intentional. The next project (MLflow Tracking Server) installs MLflow and
this problem disappears. You will appreciate MLflow more for having done it the hard way first.

## What metadata.json gives you

Every run is self-describing. You can always reconstruct what happened by reading the JSON,
even if you lost the training logs. The `model_path` field lets `compare.py` find and load
the model for inference without searching.

## What metadata.json does NOT give you

- Git SHA of the code that produced the run (did you change train_variant.py between runs?)
- Input data hash (was `adult.data` the same file?)
- System metrics (CPU usage, memory peak)
- Artifacts other than the model (preprocessor, feature names)
- Search by arbitrary metadata fields

MLflow tracks all of these out of the box.

## The timestamp collision risk

`generate_run_id()` uses seconds precision. If two runs start in the same second (e.g., in
a parallel grid search), their directories would collide. The `train_all.py` script waits
2 seconds between runs to avoid this. In production, use a UUID or MLflow's run_id.

## Interview framing

"I've done manual experiment tracking with JSON metadata files and know exactly why it breaks
down: no central search, no input data versioning, no code versioning, collision risk in parallel
runs. That's why I use MLflow — not because it's trendy, but because I've felt what it replaces."

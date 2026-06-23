# P3-11 — Retraining Pipeline

Automated ML pipeline: S3 upload → preprocess → train → evaluate → conditional deploy.

> Part of [Path 3 — ML Engineering on AWS](https://confidentprep.com/paths/path-3) on Confident Prep — see the full curriculum and how this project fits in.

## Architecture

```
S3 upload → Lambda trigger → Step Functions execution
  → State 1: SageMaker Processing (preprocess)
  → State 2: SageMaker Training
  → State 3: Lambda evaluate (compare to SSM baseline)
  → State 4: Choice (deploy if AUC improved > 1%)
  → State 5a: SageMaker deploy + SNS notify
  → State 5b: SNS notify (no deploy)
```

## Prerequisites

- Python 3.11+
- AWS credentials with: Step Functions, Lambda, SageMaker, S3, SNS, SSM, IAM permissions
- SNS topic created: `aws sns create-topic --name p3-11-ml-notifications`

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in all ARNs and names

# Deploy infrastructure
python src/state_machine.py --create
python src/s3_trigger.py --configure

# Test end-to-end
python src/test_pipeline.py
```

## Tests

```bash
pytest tests/ -v
```

7/7 passing. Tests do not make AWS API calls (mocked where AWS would be involved).

## TEARDOWN

```bash
bash scripts/teardown.sh
```

## Status: AWS-touching steps unverified — needs a real AWS account

`state_machine.py`'s real `create_state_machine`/`start_execution`/`wait_for_execution`
(Step Functions), `lambda_evaluator.py`'s real `deploy_lambda`/`get_training_job_auc`
(CloudWatch Logs)/`get_baseline_auc` (SSM), `s3_trigger.py`'s real Lambda deployment + S3
notification configuration, and `test_pipeline.py`'s full end-to-end run are all
implemented per spec but were never executed against real AWS in this environment —
there is no AWS account here at all (no Step Functions, no Lambda, no SageMaker, no S3,
no SNS, no SSM). Same precedent as `model-monitoring/` and `ab-testing/`.

**What *was* verified for real, with zero AWS:**

- The ASL state machine definition has zero AWS dependency to validate structurally —
  loaded the real `src/state_machine_definition.json` file directly (not a test fixture)
  and parsed it with `json.loads()`. It parses as valid JSON, `StartAt == "Preprocess"`,
  and the `States` object has **7** top-level keys: `Preprocess`, `Train`, `Evaluate`,
  `ShouldDeploy`, `Deploy`, `NotifyDeployed`, `NotifyNoDeploy`. (The pipeline is "5-state"
  at the logical-stage level described in the architecture diagram above — preprocess,
  train, evaluate, conditional branch, deploy-or-notify — but the Choice state and its two
  notify branches are each their own ASL state, so the literal key count is 7, not 5. This
  matches the spec's own verbatim JSON exactly.)
- `evaluate_improvement` is a pure decision function with zero AWS dependency. Run for
  real with the spec's two boundary cases: `evaluate_improvement(new_auc=0.895,
  baseline_auc=0.880, threshold=0.01)` returned `deploy=True` with `delta≈0.015`;
  `evaluate_improvement(new_auc=0.890, baseline_auc=0.880, threshold=0.01)` returned
  `deploy=False` with `delta≈0.010` — exactly at the threshold, correctly not deployed
  since the rule requires strictly greater than threshold, not greater-or-equal.
  Then run with a real cross-project number: this repo's `ab-testing/` project measured a
  **real** challenger AUC of **0.9294** against a **real** baseline AUC of **0.9289** (from
  the shared MLflow registry, val_auc 0.9288787141179664) — delta ≈ +0.0005.
  `evaluate_improvement(new_auc=0.9294, baseline_auc=0.9289, threshold=0.01)` returns
  `deploy=False` with reason `"AUC improved by only 0.0005 (threshold 0.01)"` — confirming
  that the real `ab-testing` decision ("keep current") and this project's real decision
  logic agree on the same real numbers. Not a coincidence: it's the same underlying rule
  (require AUC improvement strictly greater than 0.01 before shipping a new model)
  evaluated independently in two different projects.
- The S3-trigger Lambda's inline code string (the literal `TRIGGER_LAMBDA_CODE` in
  `s3_trigger.py`'s `create_trigger_lambda`) has zero AWS dependency to validate
  syntactically. Extracted the real string and ran it through both `compile(code,
  "<trigger_lambda>", "exec")` and `ast.parse(code)` before it is ever zipped and
  uploaded to Lambda — both succeeded, confirming the code is syntactically valid Python
  3 with exactly one top-level function (`handler`).

## A floating-point bug this project's own pytest run caught

The boundary-case test (`new_auc=0.890, baseline_auc=0.880, threshold=0.01`, expected
`deploy=False`) initially **failed** under a naive `delta > threshold` comparison:
`0.890 - 0.880` evaluates to `0.010000000000000009` in IEEE 754 double precision, not
exactly `0.01`, so the raw comparison returned `True` instead of the intended `False`.
Fixed by rounding `delta` to 4 decimal places (matching the precision AUC is reported and
stored at throughout this project) before the strict-greater-than check, in
`lambda_evaluator.py::evaluate_improvement`. This does not change the returned `delta`
value (still the full-precision float) — only the deploy/no-deploy decision boundary.

## Dependency check

`pip install -r requirements.txt` (including the spec's `xgboost==2.1.3`) installs
cleanly in a fresh venv with no resolver conflicts. Unlike `experiment-tracking/`,
`batch-inference/`, `model-serving/`, and `ab-testing/` — which all load a real
xgboost model via `XGBClassifier.load_model()` or `mlflow.xgboost.load_model()` and hit
the `xgboost==2.1.3` / `scikit-learn==1.6.0` incompatibility — nothing in this project's
own Python code calls either function. The actual model training in this pipeline happens
inside a SageMaker-managed Docker container via the Step Functions `createTrainingJob.sync`
task; this repo's code only orchestrates that job, it never loads the resulting model
artifact locally. Confirmed by grepping `src/` for `load_model` and for any `xgboost`
import — zero matches. The spec also doesn't pin `numpy` here, so there is no
numpy/sagemaker resolver conflict to fix either (unlike `model-monitoring/`'s
`requirements.txt`, which does need an unpinned numpy).

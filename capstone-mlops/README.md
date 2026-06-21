# P3-12 — Capstone: Full MLOps Loop

Wire p3-07 through p3-11 into a complete, observable MLOps system.

## WARNING

This project runs ALL components simultaneously. Combined cost: ~$5-10 for a 2-hour session.
Run `bash scripts/teardown_all.sh` immediately when done.

**No AWS account exists in this build environment, and none of p3-07 through p3-11's AWS
resources were ever actually created in real AWS at any point in this build sequence** —
every one of those projects was built code-complete with its AWS calls documented as
unverified, the same precedent this project follows. That means this capstone's own
prerequisite ("all components must be running") was never actually satisfiable here from
day one. If you run `python src/verify_components.py` against a real AWS account right now
with nothing deployed, it will correctly report all 4 components MISSING and exit 1 — that
is the expected, documented end-state for this entire zero-AWS-account build, not a bug in
this project.

## Prerequisites

All of these must be running (in a real AWS account):
- p3-07: SageMaker endpoint (InService)
- p3-10: Model Monitor schedule (Scheduled)
- p3-11: Step Functions state machine + Lambda (active)
- p3-05: MLflow server with "production" alias

Check with: `python src/verify_components.py`

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # verify all names match prior projects

# Verify everything is live
python src/verify_components.py

# Run end-to-end test
python src/end_to_end_test.py

# View costs
python src/cost_dashboard.py
```

## Architecture

See `docs/architecture.md` for the Mermaid diagram of the full loop.

## Runbook

See `docs/runbook.md` for what to do when things break.

## COMPLETE TEARDOWN

```bash
bash scripts/teardown_all.sh
```

Deletes every resource from p3-07 through p3-12 in dependency order.

## Tests

```bash
pytest tests/ -v
```

6/6 passing. Tests do not make AWS API calls (mocked where AWS would be involved).

## Status: AWS-touching steps unverified — needs a real AWS account

`verify_components.py`'s four `check_*` functions (SageMaker `describe_endpoint`,
`describe_monitoring_schedule`, Step Functions `describe_state_machine`, Lambda
`get_function`), `end_to_end_test.py`'s `inject_drift`/`check_alarm_status`/
`trigger_pipeline`/`wait_for_execution`/`verify_endpoint_predictions` (SageMaker runtime,
CloudWatch, Step Functions), and `cost_dashboard.py`'s `fetch_cost_by_service` (Cost
Explorer) are all implemented per spec but were never executed against real AWS in this
environment — there is no AWS account here at all. Same precedent as every other Path 3
project (`model-monitoring/`, `ab-testing/`, `retraining-pipeline/`, etc.).

**Be honest about what this project actually is:** unlike `model-monitoring/` (real drift
math: mean/std computation, distance metrics) or `retraining-pipeline/` (a real decision
rule: `evaluate_improvement`), this capstone's three main scripts —
`verify_components.py`, `end_to_end_test.py`, `cost_dashboard.py` — are essentially 100%
AWS-dependent glue code. Every substantive function either calls boto3 directly or wraps a
boto3 call from an earlier project. There is no comparable AWS-free core logic to verify
for real here.

**What *was* verified for real, with zero AWS:**

- `print_component_table` and `print_cost_table` are pure formatting functions with zero
  AWS dependency. Ran both directly with synthetic-but-realistic inputs (not the test's
  mocked inputs): `print_cost_table` given costs for only 2 of the 6 dashboard services
  still printed all 6 rows, with the 4 missing services correctly defaulting to `$0.0000`
  and the `TOTAL` row correctly summing only the real costs. `print_component_table` given
  a mix of `ok=True`/`ok=False` components printed `[OK]` / `[MISSING]` per component and
  `COMPONENTS MISSING` as the overall summary line, matching the spec's example layout.
- `docs/architecture.md` and `docs/runbook.md` were opened and read directly (not through
  a test mock): `architecture.md` contains exactly one fenced ` ```mermaid ` block with
  `graph LR` inside it; `runbook.md` contains exactly 4 `## Failure Scenario` headers
  (Endpoint down, retraining pipeline fails after alarm, concept drift without alarm, cost
  spike) — meeting the spec's "at least 4" requirement exactly, not by a wide margin.

## Dependency check

`pip install -r requirements.txt` with the spec's literal pins (including
`numpy==2.2.1`) fails in a fresh venv: `sagemaker==2.236.0` requires `numpy<2.0`, so pip's
resolver reports `ResolutionImpossible`. Fixed the same way as `batch-inference/`,
`model-serving/`, `ab-testing/`, and `model-monitoring/` — left `numpy` unpinned so pip
picks a sagemaker-compatible version (resolved to `numpy==1.26.4` in testing). Confirmed
clean otherwise: `xgboost==2.1.3` installs without conflict, and grepping `src/` for
`load_model` or any `xgboost` import returns zero matches — this project's own code never
loads a model artifact directly, it only orchestrates SageMaker-managed jobs and sends CSV
payloads to an endpoint over the wire, exactly like `retraining-pipeline/`.

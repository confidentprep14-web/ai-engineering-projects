# Prompt Evaluation Framework

A test harness for LLM prompts. Define test cases in YAML, score responses with
an LLM judge across multiple dimensions, and get exit code 1 on failure — so you
can run it in CI.

> Part of [Path 1 — AI Engineering Fundamentals](https://confidentprep.com/paths/path-1) on Confident Prep — see the full curriculum and how this project fits in.

## Setup

```bash
cd p1-09-prompt-eval
cp .env.example .env
pip install -r requirements.txt
```

## Run

```bash
# Run a test suite
python src/main.py run --suite test_suites/qa_suite.yaml

# Compare two prompt versions
python src/main.py diff --suite test_suites/qa_suite.yaml \
    --prompt-a prompts/v1.txt --prompt-b prompts/v2.txt

# Save report
python src/main.py run --suite test_suites/qa_suite.yaml --output report.json
```

Expected output:
```
Running qa_suite (3 test cases)...

Test Case        precision  completeness  tone   PASS
─────────────────────────────────────────────────────
tc-001 Refund    4/5 ✓      3/5 ✓         5/5 ✓   ✓
tc-002 Shipping  2/5 ✗      4/5 ✓         4/5 ✓   ✗
tc-003 Locked    3/5 ✓      3/5 ✓         4/5 ✓   ✓

Summary: 2/3 passed (67%)
```

## Tests

```bash
pytest tests/ -v
```

## What to try next

- Add this to a GitHub Action: on PR, run your prompt suite and fail the build if any test fails
- Add a new dimension: "citation" — does the answer cite a source?
- Write a test suite for the RAG pipeline from p1-03

# LLM Test Generator

Generates pytest test cases for Python functions using LLM, then validates them by actually running pytest — retrying with error context on failure.

> Part of [Path 2 — AI-Augmented Engineering](https://confidentprep.com/paths/path-2) on Confident Prep — see the full curriculum and how this project fits in.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your API key

# Generate tests
python src/main.py src/my_module.py

# Generate with coverage report
python src/main.py src/my_module.py --coverage

# Allow more retries
python src/main.py src/my_module.py --max-retries 5
```

## How the retry loop works

```
Generate tests → Run pytest → Pass? → Write to file
                                 ↓ Fail
                          Inject error into next prompt → Retry (max 3)
                                 ↓ All retries fail
                          Skip function, log warning
```

## Output

- `test_<source_name>.py` — contains only tests that actually pass
- Coverage report (with `--coverage`) — branch count for each function

## Running tests

```bash
pytest tests/ -v
```

## Note on the live LLM path

The unit tests in `tests/` mock `get_completion` directly — they test the
retry loop, prompt construction, and pytest validation logic without ever
calling a real model. An actual end-to-end run of
`python src/main.py <file>` requires a configured `ANTHROPIC_API_KEY` (or
`OPENAI_API_KEY` / a running Ollama instance) and was not exercised live in
this build — there is no LLM API key configured in this environment.

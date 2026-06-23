# Code Review Bot

CLI that reads a git diff and returns structured code-review findings.

> Part of [Path 2 — AI-Augmented Engineering](https://confidentprep.com/paths/path-2) on Confident Prep — see the full curriculum and how this project fits in.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your API key
git diff HEAD~1 | python src/main.py --output table
```

## Usage

```bash
# Review a saved diff
python src/main.py --diff my.diff

# Only show HIGH severity findings
python src/main.py --diff my.diff --min-severity HIGH

# Output as JSON
python src/main.py --diff my.diff --output json --json-out results.json
```

## Finding schema

| Field | Values |
|---|---|
| severity | HIGH / MEDIUM / LOW |
| category | security / performance / correctness / style |
| file | relative path from diff header |
| line_range | e.g. "42-55" |
| finding | human-readable description |
| suggestion | concrete fix |

## Exit codes

- `0` — no HIGH findings
- `1` — at least one HIGH finding (use in CI to block merges)

## Running tests

```bash
pytest tests/ -v
```

# PR Diff Summarizer

Turns a git diff into three audience-aware outputs:
- A plain-English summary for non-technical readers
- An architecture impact paragraph for engineering managers
- A test coverage flag when tests are absent from the diff

> Part of [Path 2 — AI-Augmented Engineering](https://confidentprep.com/paths/path-2) on Confident Prep — see the full curriculum and how this project fits in.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your API key
git diff HEAD~1 | python src/main.py --title "My PR title"
```

## Usage

```bash
# Summarize a saved diff
python src/main.py --diff my.diff

# Include PR title and reviewer comments
python src/main.py --diff my.diff --title "Refactor auth module" --comments comments.txt

# Read from stdin
git diff main...feature | python src/main.py
```

## Output sections

1. **Summary** — written for a product manager or engineering manager
2. **Architecture Impact** — module-level system design changes
3. **Test Coverage Flag** — warns when no test files appear in the diff
4. **Diff Stats** — files changed, lines added/removed

## Running tests

```bash
pytest tests/ -v
```

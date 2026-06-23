# Code Documentation Generator

Reads Python files with AST, extracts function signatures and type hints, and generates a README with LLM-written documentation for every public function.

> Part of [Path 2 — AI-Augmented Engineering](https://confidentprep.com/paths/path-2) on Confident Prep — see the full curriculum and how this project fits in.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your API key

# Generate docs for a file
python src/main.py src/main.py

# Generate and write to README
python src/main.py src/ --output README.md

# Preview what would change
python src/main.py src/ --output README.md --diff
```

## What it generates

For each public function:
- What it does (1-2 sentences)
- Parameters table (Name | Type | Description)
- Return value description
- One usage example

## Rules

- Private functions (`_name`) are always skipped
- Functions with existing docstrings > 50 words skip the LLM call
- No source files are modified — read-only

## Running tests

```bash
pytest tests/ -v
```

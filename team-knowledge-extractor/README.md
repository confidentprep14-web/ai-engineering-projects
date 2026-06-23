# Team Knowledge Extractor

Extracts structured decisions from GitHub issues and ADR markdown files. Stores them in a searchable local JSON database with keyword + recency ranking.

> Part of [Path 2 — AI-Augmented Engineering](https://confidentprep.com/paths/path-2) on Confident Prep — see the full curriculum and how this project fits in.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your API key

# Extract from a folder
python src/main.py --extract docs/decisions/

# Search
python src/main.py --search "database migration"

# List all
python src/main.py --show
```

## Input formats

**GitHub Issue JSON:**
```json
{
  "number": 42,
  "title": "Switch to PostgreSQL",
  "body": "We evaluated...",
  "comments": [{"body": "Agreed"}],
  "closed_at": "2024-01-15T10:00:00Z"
}
```

**ADR Markdown:**
```markdown
# Use PostgreSQL for data storage
Date: 2024-01-15

## Decision
We chose PostgreSQL over MySQL because...
```

## Decision schema

| Field | Description |
|---|---|
| `decision` | One-sentence summary |
| `rationale` | Why this decision was made |
| `author` | GitHub username or ADR author |
| `tags` | Topic keywords (3-5) |
| `date` | ISO date |
| `source_file` | Origin file |

## Running tests

```bash
pytest tests/ -v
```

## Note on the live LLM path

The unit tests in `tests/` mock `get_json_completion` directly (in
`test_extractor.py`) — they test the GitHub-issue and ADR loaders, the
`Decision` construction logic, the keyword/recency scoring math, and the
store's dedup-by-`source_file` behavior, all without ever calling a real
model. An actual end-to-end run of `python src/main.py --extract <dir>`
requires a configured `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY` / a running
Ollama instance) and was not exercised live in this build — there is no
LLM API key configured in this environment.

The deterministic parts of the pipeline were verified directly instead:
- `load_github_issue_json` / `load_adr_markdown` against the 4 fixture
  files in `tests/fixtures/`
- `--extract tests/fixtures/issues/` runs the file-discovery and loader
  steps correctly, then fails exactly at the LLM call boundary with
  `RuntimeError: ANTHROPIC_API_KEY not set`
- `--search` and `--show` were run against a hand-seeded
  `.knowledge_store.json` (3 decisions, no LLM involved) and correctly
  returned recency-sorted listings and keyword-ranked search results —
  e.g. `--search "authentication"` ranked the OAuth2 decision first by
  combined keyword + recency score, matching the tag bonus described in
  the spec.

This mirrors the precedent set by earlier Path 2 projects in this repo
(e.g. `llm-test-generator`, `incident-summariser`) that also could not
verify their live-LLM path.

# SQL Agent

Natural language → SQL → plain English. Uses parser-based SQL validation (sqlglot AST) and a self-correcting retry loop.

> Part of [Path 2 — AI-Augmented Engineering](https://confidentprep.com/paths/path-2) on Confident Prep — see the full curriculum and how this project fits in.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your API key

# Initialize the e-commerce database
python scripts/init_db.py

# Run interactively
python src/main.py --db ecommerce.db

# Run the 10-pair test suite
python src/main.py --db ecommerce.db --test
```

## Safety model

Only SELECT statements are allowed. Validation uses the `sqlglot` AST — not regex:

```python
parsed = sqlglot.parse_one(sql)
if not isinstance(parsed, sqlglot.expressions.Select):
    raise ValueError("Only SELECT allowed")
```

## E-commerce schema

Three tables: `customers`, `products`, `orders`

See `scripts/init_db.py` for full schema and sample data.

## Retry loop

```
NL → SQL → validate → execute
                  ↓ invalid/error
             inject error into prompt → retry (max 2)
```

## Running tests

```bash
pytest tests/ -v
```

## Verified vs. unverified

- **Verified locally:** all 16 tests pass (7 sql_validator AST cases including INSERT/UPDATE/DELETE/DROP rejection and a string-literal-containing-"DROP TABLE" false-positive guard, 4 schema_inspector cases against a real temp SQLite db, 5 agent cases covering the retry loop's error-injection logic and the empty-results short circuit). `python scripts/init_db.py` creates `ecommerce.db` with 5 customers/8 products/15 orders. The CLI was manually run end-to-end: schema introspection prints `Schema loaded: 3 tables`, and `parse_and_validate` rejecting INSERT/UPDATE/DELETE/DROP before execution is exercised directly by the test suite against the real sqlglot parser (no mocking — sqlglot is a real AST parser, not the LLM boundary).
- **Explicitly left unverified:** the live LLM-generated SQL itself — no `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` configured in this environment. Both interactive mode and `--test` fail gracefully at the LLM call boundary with `RuntimeError: ANTHROPIC_API_KEY not set` (confirmed by running `--test`, which prints `[FAIL] ... | Error: ANTHROPIC_API_KEY not set` for all 10 pairs rather than crashing) — same precedent as every other Path 2 project in this repo.

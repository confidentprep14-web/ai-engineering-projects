# Docs Copilot

RAG-based documentation assistant with section-level citations, freshness tracking, and an "I don't know" threshold.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your API key

# Index your docs
python src/main.py --index docs/

# Ask a question
python src/main.py --ask "How do I reset my password?"

# Force rebuild
python src/main.py --rebuild
```

## What makes this different from basic RAG

| Feature | Basic RAG | Docs Copilot |
|---|---|---|
| Chunking | Fixed size | By section heading |
| Metadata | None | doc_title, section_heading, mtime |
| Freshness | Manual rebuild | Automatic mtime check |
| Low confidence | Returns something | Returns "I don't know" |
| Citations | Optional | Required: [source > section] |

## Citation format

Every answer includes source citations:
```
You can reset your password from the Settings page. [setup_guide > Account Settings]
```

## Running tests

```bash
pytest tests/ -v
```

## Verified vs. unverified

- **Verified locally:** all 11 tests pass (chunker metadata attachment, freshness detection, below-threshold "I don't know", citation formatting, FAISS save/load round-trip, missing-index error). CLI smoke-tested end-to-end against `tests/fixtures/docs/` — `--index`, the no-supported-files exit-0 path, and the missing-index `--ask` failure mode all behave as documented.
- **Explicitly left unverified:** the live LLM-generated answer itself — no `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` configured in this environment. `build_answer_with_citations` fails at the LLM call boundary with `RuntimeError: ANTHROPIC_API_KEY not set`, same precedent as every other Path 2 project in this repo.

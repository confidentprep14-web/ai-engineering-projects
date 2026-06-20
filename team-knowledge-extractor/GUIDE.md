# Build Guide — Team Knowledge Extractor

## Step 1 — Two input formats, one output schema

Both input formats (GitHub JSON and ADR markdown) map to the same `Decision` dataclass. Write separate loaders but a single extractor that works on normalized content:

```python
def extract_decision(raw_content, source_type, source_file):
    # raw_content has: title, body/content, date, author
    # These fields come from either loader
    prompt = build_extraction_prompt(raw_content)
    result = get_json_completion(prompt)
    return Decision(
        id=uuid4().hex[:12],
        decision=result["decision"],
        ...
    )
```

## Step 2 — The extraction prompt

System prompt:
```
You are an engineering knowledge curator.
Extract the architectural decision from this document.
Return ONLY JSON with:
{
  "decision": "one sentence describing the decision made",
  "rationale": "2-3 sentence explanation of why",
  "author": "person responsible or 'unknown'",
  "tags": ["topic1", "topic2", "topic3"],
  "date": "YYYY-MM-DD or null"
}
```

Key constraint: `decision` must be one sentence. This forces the LLM to distill, not summarize.

## Step 3 — Keyword + recency ranking (no embeddings)

```python
def score_keyword_match(query, decision):
    tokens = query.lower().split()
    if not tokens:
        return 1.0  # empty query matches everything

    text = f"{decision.decision} {decision.rationale} {' '.join(decision.tags)}".lower()
    matched = sum(1 for t in tokens if t in text)
    # bonus for tag matches
    tag_bonus = sum(1 for t in tokens if t in [tag.lower() for tag in decision.tags])
    return min(1.0, (matched + tag_bonus) / len(tokens))
```

## Step 4 — The store

Keep it simple: one JSON file, load on startup, save after every write. For hundreds of decisions this is fast enough. The key feature is duplicate detection by `source_file` — re-running `--extract` is idempotent.

## Debugging tips

- If extraction produces empty decisions, print the raw LLM response before JSON parsing
- If search returns irrelevant results, check that tags are being indexed (they get 2x weight)
- Test with `--search ""` first — this returns all results and confirms the store is loaded

## How to talk about this in an interview

**"Why no embeddings for search?"**
> This is a deliberate design choice for structured data. Decisions have explicit tags, dates, and short summaries. Keyword + tag matching is interpretable, fast, and correct for this use case. I use embeddings in the next project for unstructured documentation — that's where they earn their complexity.

**"How do you handle duplicate processing?"**
> Each decision is keyed by source file. Re-running `--extract` on the same folder updates existing decisions in place rather than creating duplicates. This makes it safe to run as a cron job.

**"What's the LLM doing in this project?"**
> Structured extraction: converting free-form GitHub issues and markdown ADRs into the same schema. That's a task where even a small, fast model does well because the output is constrained and the instructions are precise.

## What was verified vs. left unverified in this build

All 6 spec-defined tests (keyword search ranking, recency ranking, mocked
extraction producing all required `Decision` fields with a valid 12-hex-char
id, empty-query search returning all results, duplicate-`source_file`
dedup, and ADR title/date parsing) are covered by tests that mock
`get_json_completion` directly — these all pass without any API key
(20/20 tests pass, including additional edge-case coverage from the
failure-modes table). The deterministic, non-LLM parts of the full CLI
were also exercised directly: `--show` and `--search "authentication"`
against a hand-seeded 3-decision `.knowledge_store.json` correctly
returned recency-sorted listings and a keyword+tag-ranked search (OAuth2
decision ranked first), and `--extract tests/fixtures/issues/` correctly
runs file discovery and the JSON loader before failing exactly at the LLM
call boundary with `RuntimeError: ANTHROPIC_API_KEY not set`. The actual
end-to-end extraction — the live LLM call that turns the 4 fixture files
into stored `Decision` records — was **not** exercised, because no LLM
API key is configured in this build environment. This mirrors the
precedent set by earlier Path 2 projects in this repo (e.g.
`llm-test-generator`, `incident-summariser`) that also could not verify
their live-LLM path.

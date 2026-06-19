# Build Guide — PR Diff Summarizer

## Step 1 — Stats first (no LLM)

Parse diff stats before touching the LLM. This gives you:
- Context to inject into prompts ("This PR changes 12 files and adds 400 lines")
- A cheap test coverage signal (regex, no API call)
- A log line you can emit before any async work

## Step 2 — Two separate prompts, two separate system personas

Do not mix the two LLM calls:

**Summary system prompt persona:**
```
You are a technical writer translating a code change for a non-technical audience.
Write in plain English. Do not include code, variable names, or file paths.
Keep the summary under {SUMMARY_MAX_WORDS} words.
```

**Architecture impact persona:**
```
You are a software architect reviewing a pull request for system design impact.
Describe module boundaries, data flow changes, and any new dependencies introduced.
One paragraph, under {ARCH_MAX_WORDS} words.
```

Using separate calls gives better results than asking for both in one prompt.

## Step 3 — Test coverage without LLM

```python
TEST_PATTERNS = ["test_", "_test.py", "/tests/"]

def detect_test_changes(diff_text: str) -> bool:
    filenames = extract_filenames(diff_text)
    has_tests = any(
        any(p in f for p in TEST_PATTERNS)
        for f in filenames
    )
    return not has_tests  # True = flag raised = missing tests
```

## Step 4 — Post-process for no raw code

After each LLM call, strip lines that start with `+` or `-` (they're raw diff noise the model sometimes echoes back). This is a cheap guard that makes output always safe to show to non-engineers.

## Step 5 — Compose the report

Write `build_report` to accept strings and return a formatted markdown string. This makes it trivially testable — no mocking needed, just string assertions.

## Debugging tips

- If summaries are too technical, strengthen the system prompt: add "Do not mention function names, variable names, or file paths."
- For arch impact, if the model is vague, inject the stats dict as context: "The diff changes 8 files including auth.py and database.py."
- Diff fixture files in `tests/fixtures/` should be real diffs — generate them with `git diff` on a real commit.

## How to talk about this in an interview

**"Why two separate LLM calls?"**
> Audience-aware generation. The non-technical summary needs one persona (writer, avoid jargon), the architecture paragraph needs another (architect, use technical terms). Mixing them produces mediocre output for both. Keeping them separate also lets me tune each prompt independently.

**"How did you handle test coverage detection?"**
> I do it without an LLM — regex on the filenames extracted from the diff headers. It's faster, cheaper, and more reliable than asking the model to infer it. The LLM is used only for the tasks it does uniquely well: generating natural language.

**"What would you add to make this production-ready?"**
> Post it directly as a GitHub PR comment via the PyGithub API. Add a Slack webhook integration. Cache by diff hash so re-running on the same diff is free.

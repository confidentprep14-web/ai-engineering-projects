# Build Guide — Code Review Bot

## Step 1 — Parse the diff (chunker.py logic)

A unified diff looks like:

```
diff --git a/auth.py b/auth.py
index abc..def 100644
--- a/auth.py
+++ b/auth.py
@@ -10,6 +10,8 @@ def login():
+    password = "hunter2"
```

Split on `diff --git` lines. Each resulting chunk is one file review unit.

## Step 2 — Build the LLM prompt

System prompt:
```
You are a senior engineer performing a security and quality code review.
Return ONLY a JSON array. Each element must have:
  file, line_range, severity (HIGH|MEDIUM|LOW),
  category (security|performance|correctness|style),
  finding, suggestion.
If there are no issues, return [].
```

User content: the raw diff chunk for one file.

## Step 3 — Parse and filter

- Strip any ```json ... ``` fences before parsing
- Filter by min_severity after receiving results
- If JSON parse fails: log a warning, return [] (never crash)

## Step 4 — Merge and display

- Flatten all per-chunk results
- Sort: HIGH > MEDIUM > LOW
- Deduplicate on (file, line_range, category)

## Step 5 — Wire the CLI

Use argparse. Reading from stdin (`sys.stdin.read()`) lets users pipe:
```bash
git diff HEAD~1 | python src/main.py
```

## Debugging tips

- Print the raw LLM response before parsing to diagnose JSON errors
- Use `--min-severity HIGH` when developing to reduce noise
- Start with a tiny 5-line diff to confirm JSON mode is working

## How to talk about this in an interview

**"What problem does this solve?"**
> Manual code review is inconsistent and slow. This bot gives a first-pass review in seconds, catches classes of issues humans miss when fatigued (hardcoded secrets, N+1 patterns), and integrates into CI via exit codes.

**"How did you handle large diffs?"**
> I chunk per file. Each LLM call sees only one file's changes, so context window limits never apply to the whole PR.

**"How do you ensure the output is structured?"**
> System prompt enforces a JSON schema. After receiving the response, I validate each required key exists and the severity value is one of the three allowed values before showing results.

**"How would you make this production-grade?"**
> Add a schema validation step (jsonschema), cache results per file hash to avoid re-reviewing unchanged files, and publish findings to a GitHub PR comment via PyGithub.

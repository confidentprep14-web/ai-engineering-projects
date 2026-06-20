# Build Guide — Incident Summariser

## Step 1 — Stream, don't load

Never use `f.readlines()` or `f.read()` on a large log file. Stream line by line:

```python
def stream_filter_errors(filepath):
    total = 0
    filtered = []
    in_stack_trace = False

    with open(filepath, encoding="utf-8", errors="replace") as f:
        for line in f:          # streams — no full load
            total += 1
            is_error = any(p in line for p in ERROR_PATTERNS)
            is_stack_line = line.startswith((" ", "\t")) or line.strip().startswith("at ")

            if is_error:
                filtered.append(line.rstrip())
                in_stack_trace = True
            elif in_stack_trace and is_stack_line:
                filtered.append(line.rstrip())
            else:
                in_stack_trace = False

    return filtered, total
```

## Step 2 — Always log the reduction

Before calling the LLM, log:
```python
pct = calculate_reduction_pct(total, len(filtered))
print(f"[{service}] {total} lines → {len(filtered)} filtered ({pct}% reduction)")
```

This is the key interview talking point: "I reduced token usage by over 80% before the LLM ever sees the data."

## Step 3 — The incident prompt

System prompt:
```
You are an SRE analyzing logs to produce an incident report.
Return ONLY valid JSON with this schema:
{
  "timeline": [{"timestamp": "...", "event": "..."}],
  "root_cause": {"hypothesis": "...", "confidence": 0.0-1.0, "evidence": []},
  "action_items": [{"priority": "HIGH|MEDIUM|LOW", "description": "..."}]
}
```

## Step 4 — Multi-service correlation

For each file, tag lines with the service name (basename without extension).
After filtering, merge all tagged lines into one list and sort by timestamp.
The LLM receives `[auth] 10:00:02 ERROR ...` lines alongside `[db] 10:00:05 ERROR ...` lines — cross-service correlation in one prompt.

## Step 5 — Validate confidence

Always clamp confidence to 0-1:
```python
confidence = max(0.0, min(1.0, float(raw["root_cause"]["confidence"])))
```

## How to talk about this in an interview

**"How do you handle 100MB log files?"**
> Streaming read — I never load the full file into memory. I filter line by line with regex, keeping only ERROR/WARN/exception lines and their stack traces. That reduces a 100MB file to a few hundred lines before any LLM call.

**"What's the token reduction?"**
> On my test fixture, 84.2% — 1000 lines down to 158. I log this explicitly so the number is visible in every run.

**"How do you handle multiple services?"**
> I tag each line with its service name, then merge and sort by timestamp. The LLM sees a unified timeline: `[auth] ERROR ...` followed by `[db] WARN ...`. Cross-service patterns emerge naturally.

## What was verified vs. left unverified in this build

All 6 spec-defined behaviors (pre-filter extraction, 1000-line reduction
percentage, structured-output keys, confidence clamping, multi-service
timestamp merge, stack-trace capture) are covered by tests that mock
`get_json_completion` directly — these all pass without any API key. The
deterministic part of the full CLI pipeline (streaming pre-filter,
reduction-percentage logging, multi-file timestamp correlation, and line
capping) was also exercised directly by running
`python src/main.py tests/fixtures/app.log tests/fixtures/db.log`, which
correctly prints `[app] 1000 lines → 158 filtered (84.2% reduction)` and
`[db] 500 lines → 69 filtered (86.2% reduction)`, merges both files into a
227-line timestamp-sorted sequence, and then fails exactly at the LLM
call boundary with `RuntimeError: ANTHROPIC_API_KEY not set`. The actual
end-to-end summarization — the live LLM call that turns those filtered
lines into a timeline/root-cause/action-items report — was **not**
exercised, because no LLM API key is configured in this build
environment. This mirrors the precedent set by earlier Path 2 projects in
this repo (e.g. `llm-test-generator`, `llm-observability`) that also
could not verify their live-LLM path.

# AI-Powered GitHub Action (Capstone)

GitHub Action that runs AI code review and test generation on every PR.
Posts findings as comments. HIGH finding → PR check fails.

## Deployment status

**Status: unverified end-to-end — needs a real GitHub repo/PR and an LLM API key.**
This project was built and tested in an environment with no `ANTHROPIC_API_KEY` /
`OPENAI_API_KEY` configured, and the `act` CLI (for local GitHub Actions runs) is
not installed here. What *was* verified without either of those:

- All unit tests in `tests/` — 7/7 passing locally (6 required by spec; `check_severity_gate`
  is covered by two focused tests instead of one). No real LLM or GitHub API calls in any
  test — the LLM boundary and PyGithub posting are exercised through monkeypatching/dry-run.
- `python src/action_runner.py --diff tests/fixtures/sample.diff --dry-run` with no API
  keys set: every LLM call fails with `RuntimeError("ANTHROPIC_API_KEY not set")`, is caught,
  logged as a warning, and the run completes with exit code 0 — confirms the action does not
  crash at the API-key boundary.
- The same command with `run_code_review` monkeypatched to return a synthetic HIGH finding
  (simulating what a real LLM review of `tests/fixtures/sample.diff`'s hardcoded password in
  `auth.py` should produce): the dry-run comment body prints the `🔴 HIGH` row correctly, the
  severity gate triggers, and the process exits with code **1** — confirms the full pipeline
  (findings → markdown comment → severity gate → `sys.exit`) end-to-end.
- The OTEL cost span: with `OTEL_EXPORTER=console`, `cost_tracker.py` prints a full console
  span (`pr.number`, `pr.repo`, `llm.model`, `llm.calls`, `llm.total_cost_usd`, `trace_id`,
  etc.) and the `PR Review Cost | pr=... | calls=... | tokens=... | cost=$... | trace_id=...`
  line, in both the clean-diff and gate-triggered runs.
- Config fallback: deleting/renaming `.aiworkflow.yml` (tested via `--config <missing path>`)
  prints `Config not found, using defaults` and proceeds with all tools enabled.
- Empty diff: `--diff <empty file>` prints `Empty diff — nothing to review.` and exits 0.

What was **not** run for real, because no GitHub repo/PR or LLM key exists in this build
environment:

| Component | Status |
|---|---|
| `src/llm.py` real Anthropic/OpenAI/Ollama calls | Unverified — needs an API key |
| `src/pr_commenter.py` real `PyGithub` posting (`post_comment` with `post_comments=True`) | Unverified — needs `GITHUB_TOKEN` + a real PR |
| `.github/workflows/ai-review.yml` running on an actual `pull_request` event | Unverified — needs a GitHub repo with the workflow committed and a PR opened |
| `scripts/local_test.sh` / `act` | Unverified — `act` CLI is not installed on this machine |

If you have an Anthropic/OpenAI key and a GitHub repo: add the key as a repository secret,
commit `.github/workflows/ai-review.yml`, open a PR, and the Action will run for real. To
test locally first, install `act` (`brew install act`) and run `bash scripts/local_test.sh`.

This is the same standing precedent as `aws-lambda-deploy/` and `ai-assistant-capstone/`
elsewhere in this repo: 🔴-difficulty projects that require external infrastructure this
build environment doesn't have are built and tested as far as locally possible, with the
remaining integration boundary documented rather than faked.

## Setup

1. Add `ANTHROPIC_API_KEY` to your repository's **Settings → Secrets and variables → Actions**
2. Commit `.github/workflows/ai-review.yml` to your repository
3. Open a PR — the Action runs automatically

## What it does

On every PR:
1. **Code Review** — scans the diff for security, performance, correctness, and style issues
2. **Test Generation** — generates pytest tests for changed Python functions
3. **Severity Gate** — exits with code 1 if any HIGH finding is found (blocks merge)
4. **OTEL Tracking** — records model, tokens, cost, and latency per PR review

## PR comment format

**Code Review:**

| Severity | File | Lines | Category | Finding |
|---|---|---|---|---|
| 🔴 HIGH | auth.py | 12-15 | security | Hardcoded password |

**Test Generation:**

- Functions analyzed: 3
- Tests generated: 8
- Coverage: 72%

## Local testing

```bash
# Install act: https://github.com/nektos/act
bash scripts/local_test.sh
```

## Configuration

Edit `.aiworkflow.yml`:

```yaml
ai_review:
  code_review:
    severity_gate: HIGH   # Change to MEDIUM to be stricter
  test_generation:
    enabled: false        # Disable test gen for large PRs
```

## Running tests

```bash
source .venv/bin/activate
pytest tests/ -v
```

7/7 tests pass locally (6 required by spec) — covers the severity gate (HIGH triggers,
MEDIUM-only does not), the config enable/disable flags in `main()`, the markdown formatters
for both PR comment types, dry-run comment posting, and the OTEL span attributes recorded by
`PRCostTracker`.

## What to try next

- Point `LLM_PROVIDER`/`LLM_MODEL` at a real Anthropic key and open a real PR with a
  hardcoded secret to see the severity gate actually block a merge
- Wire `OTEL_EXPORTER=jaeger` to a local Jaeger collector and watch cost accumulate across PRs
- Add a `coverage_pct` calculation to `run_test_generation` by actually running pytest
  against the generated tests instead of leaving it `None`

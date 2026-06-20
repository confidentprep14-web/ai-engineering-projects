# Build Guide — AI-Powered GitHub Action

## Step 1 — Understand the GitHub Actions environment

When a PR is opened, the Action:
1. Checks out the code
2. Generates a diff with `git diff origin/${{ github.base_ref }}...HEAD`
3. Passes it to `python src/action_runner.py --diff /tmp/pr.diff`
4. The Python script has access to env vars: `GITHUB_TOKEN`, `PR_NUMBER`, `REPO_NAME`

The Python process's exit code controls the PR check:
- Exit 0 → check passes → merge allowed
- Exit 1 → check fails → merge blocked

## Step 2 — Posting PR comments

Use PyGithub:

```python
from github import Github

def post_comment(body, pr_number, repo_name, github_token):
    g = Github(github_token)
    repo = g.get_repo(repo_name)
    pr = repo.get_pull(int(pr_number))
    comment = pr.create_issue_comment(body)
    return comment.html_url
```

The `GITHUB_TOKEN` is automatically provided by GitHub Actions — you don't need a personal access token for commenting on the same repo.

## Step 3 — The severity gate

```python
SEVERITY_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}

def check_severity_gate(findings, gate_level):
    gate_value = SEVERITY_ORDER.get(gate_level, 2)
    return any(
        SEVERITY_ORDER.get(f["severity"], 0) >= gate_value
        for f in findings
    )
```

After all tools run, check the gate. If triggered:
```python
if check_severity_gate(findings, config["code_review"]["severity_gate"]):
    print("Severity gate triggered: HIGH finding found.")
    sys.exit(1)
```

## Step 4 — OTEL instrumentation

Record cost and latency per PR, not per call:

```python
with tracer.start_as_current_span("ai_review.pr") as span:
    span.set_attribute("pr.number", pr_number)
    span.set_attribute("llm.total_cost_usd", total_cost)
    span.set_attribute("llm.calls", call_count)
    span.set_attribute("trace_id", trace_id)
```

This gives you one span per PR to track aggregate cost and performance over time.

## Step 5 — Local testing with act

`act` runs GitHub Actions locally using Docker. Install it, then:

```bash
act pull_request \
    --secret ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
    --secret GITHUB_TOKEN="$GITHUB_TOKEN" \
    --env PR_NUMBER=1 \
    --env REPO_NAME="owner/repo" \
    -j ai-review
```

The `--dry-run` flag skips Docker and just validates the workflow YAML.

**Build-environment note:** `act` is not installed in the environment this project was
built in (no Docker-backed local Actions runner available), the same constraint that
applies to `aws-lambda-deploy/`'s AWS CLI and `ai-assistant-capstone/`'s cloud
dependencies elsewhere in this repo. The workflow YAML and `local_test.sh` script are
implemented exactly per spec and are ready to run as-is on a machine with `act` and
Docker installed — see this project's `README.md` → "Deployment status" for exactly
what was and wasn't exercised here.

## Step 6 — Dry-run mode for development

Set `post_comments: false` in `.aiworkflow.yml` during development. This prints the comment body to stdout instead of calling the GitHub API — essential for local testing without a real PR.

## Debugging tips

- If the Action fails with "git diff returned no output", the `fetch-depth: 0` option in the workflow YAML is required — add it to `actions/checkout`
- If GITHUB_TOKEN lacks permission to post comments, check that `permissions: pull-requests: write` is in the workflow
- If `act` can't find Docker, use `act --platform ubuntu-latest=catthehacker/ubuntu:act-latest`

## How to talk about this in an interview

**"Why package AI tools as a GitHub Action instead of just a CLI?"**
> Integration. The value of a code review tool is zero if engineers don't use it. By running on every PR automatically and posting results as comments, it's part of the workflow without requiring any behavior change from developers.

**"What does the severity gate buy you?"**
> It's the difference between a suggestion and a guardrail. Findings without consequence get ignored. A HIGH finding that blocks the PR merge forces a decision: fix it or dismiss it explicitly. Either way, the team has a record.

**"How do you prevent the Action from becoming too slow?"**
> Two levers. First, review only the changed files — don't re-review unchanged code. Second, the `test_generation.enabled` flag in config lets teams disable test gen on large PRs where it would be slow. Cost and latency are logged per run so you can see where time is going.

**"How do you track cost over time?"**
> Each PR review creates an OTEL span with total cost and tokens. If you export to a time-series database, you can plot cost per PR, cost per author, and cost trend as the codebase grows. I log the trace ID in the PR comment so you can look up the full span for any PR.

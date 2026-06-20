"""Markdown comment formatting + posting to GitHub.

format_review_comment / format_test_results_comment build the markdown
bodies. post_comment is the actual GitHub API call (via PyGithub) — or,
in dry-run mode (settings.post_comments=False), it just prints the body
and returns "dry-run" so local development never needs a real token.
"""

import os

SEVERITY_EMOJI = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}


def format_review_comment(findings: list[dict], trace_id: str) -> str:
    """Build the markdown PR comment for code-review findings."""
    model = os.environ.get("LLM_MODEL", "")

    lines = [
        "## AI Code Review",
        "",
        "| Severity | File | Lines | Category | Finding | Suggestion |",
        "|---|---|---|---|---|---|",
    ]

    counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for finding in findings:
        severity = str(finding.get("severity", "LOW")).upper()
        counts[severity] = counts.get(severity, 0) + 1
        emoji = SEVERITY_EMOJI.get(severity, "")
        lines.append(
            f"| {emoji} {severity} | {finding.get('file', '')} | "
            f"{finding.get('line_range', '')} | {finding.get('category', '')} | "
            f"{finding.get('finding', '')} | {finding.get('suggestion', '')} |"
        )

    lines.append("")
    lines.append(
        f"**Summary:** {counts['HIGH']} HIGH, {counts['MEDIUM']} MEDIUM, {counts['LOW']} LOW findings"
    )
    lines.append("")
    lines.append(f"_Trace ID: {trace_id} | Model: {model}_")

    return "\n".join(lines)


def format_test_results_comment(results: dict, trace_id: str) -> str:
    """Build the markdown PR comment for test-generation results."""
    coverage = results.get("coverage_pct")
    coverage_str = f"{coverage}%" if coverage is not None else "N/A"

    lines = [
        "## AI Test Generation Results",
        "",
        f"- Functions analyzed: {results.get('functions_tested', 0)}",
        f"- Tests generated: {results.get('tests_generated', 0)}",
        f"- Retries needed: {results.get('retries', 0)}",
        f"- Coverage: {coverage_str}",
        "",
        f"_Trace ID: {trace_id}_",
    ]
    return "\n".join(lines)


def post_comment(body: str, pr_number: int, repo_name: str, github_token: str, post_comments: bool = True) -> str:
    """Post a markdown comment to a PR via PyGithub.

    If post_comments is False, log the body to stdout and return
    "dry-run" instead of calling the GitHub API. If post_comments is True
    but no github_token is available, raise EnvironmentError (per spec —
    posting was requested but the Action has no way to do it).
    """
    if not post_comments:
        print("--- DRY RUN: PR comment body ---")
        print(body)
        print("--- END DRY RUN ---")
        return "dry-run"

    if not github_token:
        raise EnvironmentError(
            "GITHUB_TOKEN not set but post_comments=true. "
            "Add GITHUB_TOKEN to repository secrets or set post_comments: false in .aiworkflow.yml."
        )

    from github import Github
    from github import GithubException

    try:
        g = Github(github_token)
        repo = g.get_repo(repo_name)
        pr = repo.get_pull(int(pr_number))
        comment = pr.create_issue_comment(body)
        return comment.html_url
    except GithubException as exc:
        print(f"Warning: GitHub API call failed while posting comment ({exc}); continuing.")
        return "post-failed"


def post_review_comment(findings: list[dict], trace_id: str, config: dict) -> None:
    """Format the review findings and post (or dry-run) the comment."""
    settings = config.get("settings", {})
    post_comments = settings.get("post_comments", True)
    comment_on_pass = settings.get("comment_on_pass", False)

    if not findings and not comment_on_pass:
        print("No findings and comment_on_pass=false — skipping review comment.")
        return

    body = format_review_comment(findings, trace_id)
    post_comment(
        body,
        pr_number=os.environ.get("PR_NUMBER", ""),
        repo_name=os.environ.get("REPO_NAME", ""),
        github_token=os.environ.get("GITHUB_TOKEN", ""),
        post_comments=post_comments,
    )


def post_test_results(results: dict, trace_id: str, config: dict) -> None:
    """Format the test-generation results and post (or dry-run) the comment."""
    settings = config.get("settings", {})
    post_comments = settings.get("post_comments", True)

    body = format_test_results_comment(results, trace_id)
    post_comment(
        body,
        pr_number=os.environ.get("PR_NUMBER", ""),
        repo_name=os.environ.get("REPO_NAME", ""),
        github_token=os.environ.get("GITHUB_TOKEN", ""),
        post_comments=post_comments,
    )

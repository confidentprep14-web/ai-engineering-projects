"""Tests for action_runner.py: severity gate logic and config enable/disable flags."""

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

import action_runner  # noqa: E402
from action_runner import check_severity_gate, main  # noqa: E402


# ---------------------------------------------------------------------------
# Test 1 — Severity gate logic: HIGH triggers, MEDIUM-only does not
# ---------------------------------------------------------------------------


def test_severity_gate_triggers_on_high_finding():
    findings = [
        {"severity": "LOW", "file": "a.py"},
        {"severity": "HIGH", "file": "b.py"},
    ]
    assert check_severity_gate(findings, "HIGH") is True


def test_severity_gate_not_triggered_by_medium_only():
    findings = [
        {"severity": "MEDIUM", "file": "a.py"},
        {"severity": "MEDIUM", "file": "b.py"},
    ]
    assert check_severity_gate(findings, "HIGH") is False


# ---------------------------------------------------------------------------
# Test 4 — Config respects tool enable/disable flags
# ---------------------------------------------------------------------------


def test_main_skips_disabled_code_review_but_runs_test_generation(tmp_path, monkeypatch):
    config_path = tmp_path / ".aiworkflow.yml"
    config_path.write_text(
        """
ai_review:
  code_review:
    enabled: false
    min_severity: LOW
    severity_gate: HIGH
  test_generation:
    enabled: true
    max_retries: 2
settings:
  post_comments: false
  comment_on_pass: false
"""
    )

    diff_path = tmp_path / "pr.diff"
    diff_path.write_text("diff --git a/x.py b/x.py\n@@ -0,0 +1 @@\n+def foo():\n    pass\n")

    monkeypatch.setenv("PR_NUMBER", "1")
    monkeypatch.setenv("REPO_NAME", "owner/repo")
    monkeypatch.setenv("OTEL_EXPORTER", "console")

    review_mock_called = {"called": False}
    test_gen_mock_called = {"called": False}

    def fake_run_code_review(diff_text, config, tracker):
        review_mock_called["called"] = True
        return [], 0

    def fake_run_test_generation(diff_text, config, tracker):
        test_gen_mock_called["called"] = True
        return {
            "functions_tested": 1,
            "tests_generated": 1,
            "retries": 0,
            "coverage_pct": None,
        }

    monkeypatch.setattr(action_runner, "run_code_review", fake_run_code_review)
    monkeypatch.setattr(action_runner, "run_test_generation", fake_run_test_generation)
    monkeypatch.setattr(action_runner, "post_review_comment", lambda *a, **k: None)
    monkeypatch.setattr(action_runner, "post_test_results", lambda *a, **k: None)

    try:
        main(["--diff", str(diff_path), "--config", str(config_path)])
    except SystemExit as exc:
        assert exc.code == 0

    assert review_mock_called["called"] is False
    assert test_gen_mock_called["called"] is True

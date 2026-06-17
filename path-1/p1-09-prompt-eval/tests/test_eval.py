"""Tests for the prompt evaluation framework. All LLM calls are mocked —
there is no API key configured in this environment, and judge tests must
not depend on a live model."""
import json

from src.judge import score_response
from src.reporter import save_json_report
from src.runner import load_suite

DIMENSION = {
    "name": "precision",
    "description": "Answer addresses exactly what was asked, no more",
    "passing_threshold": 3,
}


def test_load_suite_parses_yaml_correctly():
    suite = load_suite("test_suites/qa_suite.yaml")
    assert isinstance(suite["suite_name"], str)
    assert len(suite["test_cases"]) >= 3


def test_judge_returns_valid_structure(monkeypatch):
    monkeypatch.setattr(
        "src.judge.llm.get_completion",
        lambda *args, **kwargs: '{"score": 4, "reasoning": "Good answer"}',
    )
    result = score_response("some response", "some question", "some context", DIMENSION)
    assert "score" in result
    assert "passed" in result
    assert "reasoning" in result


def test_judge_handles_malformed_json(monkeypatch):
    monkeypatch.setattr(
        "src.judge.llm.get_completion", lambda *args, **kwargs: "not json"
    )
    result = score_response("some response", "some question", "some context", DIMENSION)
    assert result["score"] == 0
    assert result["passed"] is False


def test_pass_fail_threshold_applied_correctly(monkeypatch):
    monkeypatch.setattr(
        "src.judge.llm.get_completion",
        lambda *args, **kwargs: '{"score": 3, "reasoning": "Acceptable"}',
    )

    failing_dimension = {**DIMENSION, "passing_threshold": 4}
    result = score_response("resp", "q", "ctx", failing_dimension)
    assert result["passed"] is False

    passing_dimension = {**DIMENSION, "passing_threshold": 3}
    result = score_response("resp", "q", "ctx", passing_dimension)
    assert result["passed"] is True


def test_reporter_saves_valid_json(tmp_path):
    sample_result = {
        "suite_name": "Test Suite",
        "results": [{"id": "tc-001", "passed": True}],
        "summary": {"total": 1, "passed": 1, "failed": 0, "pass_rate": 1.0},
    }
    output_path = tmp_path / "report.json"

    save_json_report(sample_result, str(output_path))

    assert output_path.exists()
    with open(output_path) as f:
        loaded = json.load(f)
    assert loaded["suite_name"] == "Test Suite"

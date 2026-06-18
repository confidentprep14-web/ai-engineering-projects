import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import requests

import tools as tools_module
from tools import calculator, call_tool, get_datetime, wikipedia_search


def test_calculator_evaluates_correct_result():
    assert calculator("2 + 2 * 3") == "8"


def test_calculator_blocks_eval_injection():
    result = calculator("__import__('os').system('echo bad')")
    assert "Error" in result


def test_calculator_blocks_name_references():
    result = calculator("pi * 2")
    assert "Error" in result


def test_wikipedia_search_handles_404(monkeypatch):
    class FakeNotFoundResponse:
        status_code = 404

        def json(self):
            return {}

    monkeypatch.setattr(tools_module.requests, "get", lambda url, timeout, headers=None: FakeNotFoundResponse())

    result = wikipedia_search("Definitely Not A Real Article Title")

    assert "No Wikipedia article found" in result


def test_wikipedia_search_handles_timeout(monkeypatch):
    def fake_get_that_times_out(url, timeout, headers=None):
        raise requests.Timeout("simulated timeout")

    monkeypatch.setattr(tools_module.requests, "get", fake_get_that_times_out)

    result = wikipedia_search("Slow Article")

    assert result == "Wikipedia request timed out"


def test_call_tool_returns_error_string_for_unknown_tool():
    result = call_tool("nonexistent_tool", {})
    assert "Error" in result


def test_call_tool_never_raises_when_wrapped_function_errors():
    result = call_tool("calculator", {"expression": "1 / 0"})
    assert "Error" in result


def test_get_datetime_returns_iso_format():
    result = get_datetime()
    assert result.startswith("20")
    assert "T" in result


def test_get_datetime_ignores_unexpected_kwargs():
    result = get_datetime(format="ISO")
    assert "T" in result

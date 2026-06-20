"""Tests for src/main.py: the `ai` dispatcher's help and error-handling paths."""

import sys

import pytest

from src.main import main


def test_unknown_subcommand_prints_help_and_exits_nonzero(capsys, monkeypatch):
    """`ai unknown-tool` must print help mentioning available tools and
    exit with a non-zero status code."""
    monkeypatch.setattr(sys, "argv", ["ai", "unknown-tool"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code != 0

    captured = capsys.readouterr()
    assert "Available tools" in captured.out or "usage" in captured.out


def test_no_subcommand_lists_all_active_tools_with_descriptions(capsys, monkeypatch):
    """`ai` with no subcommand must list all 4 active tool names and
    their descriptions in the help output."""
    monkeypatch.setattr(sys, "argv", ["ai"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0

    captured = capsys.readouterr()
    for tool_name in ("review", "explain", "search", "query"):
        assert tool_name in captured.out

    assert "Code review" in captured.out
    assert "PR summarizer" in captured.out
    assert "Semantic codebase search" in captured.out
    assert "Natural language to SQL" in captured.out

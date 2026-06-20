"""Tests for src/plugin_loader.py: discovery, dynamic loading, interface validation."""

import textwrap

import pytest

from src.plugin_loader import discover_tools, get_tool_interface, load_tool_plugin


def test_discover_tools_finds_all_py_files_in_tools_dir():
    """discover_tools("tools") returns all 4 real tool files, sorted, and
    excludes __init__.py / private files."""
    names = discover_tools("tools")

    assert names == ["explain", "query", "review", "search"]
    assert "__init__" not in names
    assert all(not name.startswith("_") for name in names)


def test_load_tool_plugin_missing_attribute_raises_attribute_error(tmp_path):
    """A tool module that only defines TOOL_NAME (missing run, etc.) must
    raise AttributeError when its interface is validated."""
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    incomplete_tool = tools_dir / "incomplete.py"
    incomplete_tool.write_text(
        textwrap.dedent(
            """
            TOOL_NAME = "incomplete"
            """
        )
    )

    module = load_tool_plugin("incomplete", str(tools_dir))

    with pytest.raises(AttributeError):
        get_tool_interface(module)

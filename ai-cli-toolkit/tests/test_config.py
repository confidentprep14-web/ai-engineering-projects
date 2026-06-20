"""Tests for src/config.py: load_config, get_active_tools, get_tool_config."""

import textwrap

from src.config import get_active_tools, get_tool_config, load_config


def test_disabling_a_tool_excludes_it_from_active_tools(tmp_path):
    """A tool with enabled: false in .aiworkflow.yml must not appear in
    get_active_tools, while the other 3 default tools remain active."""
    config_path = tmp_path / ".aiworkflow.yml"
    config_path.write_text(
        textwrap.dedent(
            """
            tools:
              review:
                enabled: false
                min_severity: LOW
              explain:
                enabled: true
              search:
                enabled: true
                index_dir: .index
              query:
                enabled: true
                db_path: ecommerce.db
            """
        )
    )

    config = load_config(str(config_path))
    active = get_active_tools(config)

    assert "review" not in active
    assert "explain" in active
    assert "search" in active
    assert "query" in active


def test_get_tool_config_returns_enabled_and_tool_specific_keys():
    """get_tool_config on the default config's "review" entry returns a
    dict with enabled=True and the min_severity key."""
    config = load_config("nonexistent-config-file-for-default-fallback.yml")

    tool_config = get_tool_config(config, "review")

    assert tool_config["enabled"] is True
    assert "min_severity" in tool_config

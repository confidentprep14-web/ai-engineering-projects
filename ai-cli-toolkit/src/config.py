"""Loads and queries .aiworkflow.yml — the toolkit's tool-activation config.

load_config() reads the YAML file (falling back to a default config with
all 4 tools enabled if the file is missing). get_active_tools() and
get_tool_config() are thin accessors the dispatcher and individual tools
use to read enabled/disabled state and per-tool settings.
"""

import os

import yaml

DEFAULT_CONFIG = {
    "tools": {
        "review": {
            "enabled": True,
            "description": "Code review — finds security, performance, correctness, and style issues in a git diff",
            "min_severity": "LOW",
        },
        "explain": {
            "enabled": True,
            "description": "PR summarizer — plain-English summary, architecture impact, and test coverage flag",
        },
        "search": {
            "enabled": True,
            "description": "Semantic codebase search — find functions by meaning, not just keyword",
            "index_dir": ".index",
        },
        "query": {
            "enabled": True,
            "description": "Natural language to SQL — ask questions about your database in plain English",
            "db_path": "ecommerce.db",
        },
    },
    "settings": {
        "default_output": "table",
        "max_retries": 3,
    },
}


def load_config(config_path: str | None = None) -> dict:
    """Load .aiworkflow.yml as a dict.

    Resolution order for the path: explicit config_path argument, then
    the CONFIG_PATH env var, then the literal ".aiworkflow.yml".

    If the file does not exist, returns a default config with all 4
    tools enabled (and logs a message to stdout). If the file exists but
    is not valid YAML, or does not contain a top-level "tools" key,
    raises ValueError naming the file path.
    """
    path = config_path or os.environ.get("CONFIG_PATH", ".aiworkflow.yml")

    if not os.path.exists(path):
        print("No config file found, using defaults")
        return DEFAULT_CONFIG

    with open(path, "r", encoding="utf-8") as f:
        try:
            parsed = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            raise ValueError(f"Invalid YAML in config file: {path}") from exc

    if not isinstance(parsed, dict) or "tools" not in parsed:
        raise ValueError(f"Config file {path} is missing the required 'tools' key")

    return parsed


def get_active_tools(config: dict) -> list[str]:
    """Return the names of tools where enabled == True, in config order."""
    tools = config.get("tools", {})
    return [name for name, tool_config in tools.items() if tool_config.get("enabled") is True]


def get_tool_config(config: dict, tool_name: str) -> dict:
    """Return the sub-dict for one tool, or {"enabled": False} if absent."""
    tools = config.get("tools", {})
    return tools.get(tool_name, {"enabled": False})

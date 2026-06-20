# AI CLI Toolkit

A unified `ai` command that dispatches to AI engineering tools. Plugin architecture — add a new tool by adding one file to `tools/`.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
cp .env.example .env   # add your API key

ai review --diff my.diff
ai explain --diff my.diff --title "My PR"
ai search --query "error handling"
ai query --question "show all customers from US"
```

## Available tools

| Command | Description |
|---|---|
| `ai review` | Code review — security, performance, correctness, style |
| `ai explain` | PR summarizer — plain English + architecture impact |
| `ai search` | Semantic codebase search |
| `ai query` | Natural language to SQL |

## Configuration

Edit `.aiworkflow.yml` to enable/disable tools and set tool-specific defaults:

```yaml
tools:
  review:
    enabled: true
    min_severity: HIGH  # only show HIGH findings
  search:
    enabled: false      # disable search if no index built
```

## Adding a new tool

1. Create `tools/my_tool.py` with `TOOL_NAME`, `TOOL_DESCRIPTION`, `run(args, config)`, `add_arguments(parser)`
2. Add an entry to `.aiworkflow.yml` under `tools:`
3. Run `ai my_tool --help` — it's available immediately

## Running tests

```bash
pytest tests/ -v
```

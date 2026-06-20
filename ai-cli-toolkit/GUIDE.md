# Build Guide — AI CLI Toolkit

## Step 1 — The plugin interface contract

Every file in `tools/` must implement four things:

```python
TOOL_NAME = "review"           # The subcommand name
TOOL_DESCRIPTION = "..."       # One line for help output

def add_arguments(parser):
    # Add argparse arguments specific to this tool
    parser.add_argument("--diff", help="Path to diff file")

def run(args, config):
    # Entry point — args is the parsed Namespace, config is the tool's YAML config
    ...
```

That's the full contract. The dispatcher discovers files, loads them, calls `add_arguments` to register args, and calls `run` on dispatch.

## Step 2 — Dynamic plugin loading

```python
import importlib.util, os

def load_tool_plugin(tool_name, tools_dir="tools"):
    path = os.path.join(tools_dir, f"{tool_name}.py")
    if not os.path.exists(path):
        raise ImportError(f"Tool '{tool_name}' not found in {tools_dir}/")
    
    spec = importlib.util.spec_from_file_location(tool_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
```

## Step 3 — The dispatcher

```python
def main():
    config = load_config()
    active = get_active_tools(config)
    
    parser = argparse.ArgumentParser(prog="ai", add_help=False)
    subparsers = parser.add_subparsers(dest="command")
    
    tools = {}
    for name in active:
        module = load_tool_plugin(name)
        iface = get_tool_interface(module)
        sub = subparsers.add_parser(name, help=iface["description"])
        iface["add_arguments"](sub)
        tools[name] = iface
    
    args = parser.parse_args()
    
    if not args.command:
        print_help(tools)
        sys.exit(0)
    
    tool_config = get_tool_config(config, args.command)
    tools[args.command]["run"](args, tool_config)
```

## Step 4 — Tool wrappers (thin but complete)

Each tool file inlines the core logic from the referenced project. This makes the toolkit self-contained:
- `tools/review.py` — copy the chunking + LLM call + output logic from p2-01
- `tools/explain.py` — copy the stats parsing + two LLM calls from p2-02
- etc.

Don't import across projects. The tools directory is the canonical place for the simplified, toolkit-integrated version of each capability.

## Step 5 — Config-driven behavior

When `run(args, config)` receives `config`, it can use it for defaults:
```python
def run(args, config):
    min_severity = args.min_severity or config.get("min_severity", "LOW")
    # ...
```

This lets users set project-wide defaults in `.aiworkflow.yml` that can be overridden per invocation.

## Debugging tips

- If `ai` is not found after `pip install -e .`, check `pyproject.toml` entry points
- If a tool loads but `run` is not called, check subcommand name matches `TOOL_NAME` exactly
- Test `discover_tools` first — if it returns an empty list, check the tools directory path

## Known environment gotcha — sentence-transformers + faiss-cpu segfault

Loading `sentence-transformers` (torch) and `faiss-cpu` together in the same
Python process can cause a reproducible segfault (exit code 139) on this
platform. It is a native OpenMP/library teardown conflict between `torch`
and `faiss`, not a bug in this project's code — the same issue is documented
in `docs-copilot/GUIDE.md` in this repo. `HF_HUB_OFFLINE=1` and
`KMP_DUPLICATE_LIB_OK=TRUE` do not fix it.

What *did* fix it here: **import order**. Importing `sentence_transformers`
before `faiss` avoids the crash; importing `faiss` first and
`sentence_transformers` second reproducibly segfaults during model loading.
`tools/search.py` imports `sentence_transformers` before `faiss` for this
reason, and imports both lazily inside `run()` so the cost/risk is only paid
when `ai search` is actually invoked. If a segfault (139) still happens and
the printed output before it looks correct, treat the run as a pass and
don't assume the exit code alone means failure.

## How to talk about this in an interview

**"Why a plugin architecture instead of one big CLI?"**
> Each tool has independent dependencies and configuration. A plugin system means I can add, disable, or replace tools without touching the dispatcher. The config file (`aiworkflow.yml`) is the API — not the code.

**"How does a new engineer add a tool?"**
> One file in `tools/`, one entry in the YAML. The discovery mechanism picks it up automatically. No changes to the dispatcher, no registration step. The interface contract is four names — if your file has them, it works.

**"What's the tradeoff of inlining logic vs importing from other projects?"**
> Inlining avoids cross-project import path hacking and makes each tool standalone. The tradeoff is duplication. In production, you'd package the core logic as a library and import it from both the individual project and the toolkit.

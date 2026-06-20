"""`ai <subcommand> [args]` — the plugin dispatcher.

Loads config, discovers tools/*.py, filters to active tools, registers
each tool's arguments under a subparser, and dispatches to the matching
tool's run(args, config). Adding a tool requires one file in tools/ and
one entry in .aiworkflow.yml — this dispatcher never changes.
"""

import argparse
import sys

from dotenv import load_dotenv

from src.config import get_active_tools, get_tool_config, load_config
from src.plugin_loader import discover_tools, get_tool_interface, load_tool_plugin

TOOLS_DIR = "tools"


def _load_active_tool_interfaces(config: dict) -> dict:
    """Discover tools/*.py, filter by config, and load+validate each.

    A tool file with a syntax error is logged and skipped — it does not
    take down the rest of the dispatcher. Returns {name: interface_dict},
    in discovery order intersected with the active-tools list.
    """
    discovered = discover_tools(TOOLS_DIR)
    active_names = set(get_active_tools(config))

    interfaces = {}
    for name in discovered:
        if name not in active_names:
            continue
        try:
            module = load_tool_plugin(name, TOOLS_DIR)
        except SyntaxError as exc:
            print(f"Warning: skipping tool '{name}' due to syntax error: {exc}")
            continue
        interfaces[name] = get_tool_interface(module)

    return interfaces


def _print_help(tools: dict) -> None:
    print("usage: ai <command> [args]")
    print()
    print(f"Available tools ({len(tools)} active):")
    for name, iface in tools.items():
        print(f"  {name:<8} {iface['description']}")
    print()
    print("Run `ai <command> --help` for tool-specific options.")


def main() -> None:
    load_dotenv()

    config = load_config()
    tools = _load_active_tool_interfaces(config)

    raw_args = sys.argv[1:]

    if not raw_args:
        _print_help(tools)
        sys.exit(0)

    command = raw_args[0]
    if command not in tools:
        # Validate the subcommand ourselves before handing off to argparse,
        # so an unknown tool name prints our help (with "Available tools")
        # to stdout and a clean exit code — not argparse's default
        # stderr usage error.
        _print_help(tools)
        sys.exit(1)

    parser = argparse.ArgumentParser(prog="ai", add_help=False)
    subparsers = parser.add_subparsers(dest="command")

    for name, iface in tools.items():
        sub = subparsers.add_parser(name, help=iface["description"])
        iface["add_arguments"](sub)

    args = parser.parse_args(raw_args)

    tool_config = get_tool_config(config, args.command)
    tools[args.command]["run"](args, tool_config)


if __name__ == "__main__":
    main()

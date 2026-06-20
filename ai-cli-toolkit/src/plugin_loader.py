"""Dynamic plugin discovery and loading for tools/.

discover_tools() scans a directory for .py files and returns tool names
(no sys.path hacking — every tool file is self-contained). load_tool_plugin()
loads one file as a standalone module via importlib, independent of the
package import system. get_tool_interface() validates that a loaded module
implements the four-part plugin contract (TOOL_NAME, TOOL_DESCRIPTION, run,
add_arguments) before the dispatcher trusts it.
"""

import importlib.util
import os


def discover_tools(tools_dir: str = "tools") -> list[str]:
    """Return a sorted list of tool names (filenames without .py) in tools_dir.

    Excludes __init__.py and any file starting with "_". Returns []
    if the directory does not exist.
    """
    if not os.path.isdir(tools_dir):
        return []

    names = []
    for filename in os.listdir(tools_dir):
        if not filename.endswith(".py"):
            continue
        if filename == "__init__.py" or filename.startswith("_"):
            continue
        names.append(filename[: -len(".py")])

    return sorted(names)


def load_tool_plugin(tool_name: str, tools_dir: str = "tools"):
    """Load tools/<tool_name>.py as a standalone module and return it.

    Raises ImportError if the file does not exist. Re-raises SyntaxError
    as-is so callers (the dispatcher) can catch it, log a warning, and
    skip the tool while continuing to load others.
    """
    path = os.path.join(tools_dir, f"{tool_name}.py")
    if not os.path.exists(path):
        raise ImportError(f"Tool '{tool_name}' not found in {tools_dir}/")

    spec = importlib.util.spec_from_file_location(tool_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REQUIRED_ATTRS = ("TOOL_NAME", "TOOL_DESCRIPTION", "run", "add_arguments")


def get_tool_interface(module) -> dict:
    """Validate and extract the plugin interface from a loaded tool module.

    Every tool module must define TOOL_NAME (str), TOOL_DESCRIPTION (str),
    run(args, config), and add_arguments(parser). Raises AttributeError
    naming the first missing attribute if the contract is not met.
    """
    for attr in REQUIRED_ATTRS:
        if not hasattr(module, attr):
            raise AttributeError(
                f"Tool module '{getattr(module, '__name__', '?')}' is missing required attribute '{attr}'"
            )

    return {
        "name": module.TOOL_NAME,
        "description": module.TOOL_DESCRIPTION,
        "run": module.run,
        "add_arguments": module.add_arguments,
    }

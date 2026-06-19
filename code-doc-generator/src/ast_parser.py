"""Static analysis of Python source via the ast module.

extract_functions() never executes the target file — it parses the
source into an AST, walks FunctionDef/AsyncFunctionDef nodes, and pulls
out names, parameter metadata (name/type/default), return type, and
docstrings. This is safer than exec/importlib (no side effects, no
dependency installation) and gives the doc generator typed, structured
input instead of strings it would otherwise have to regex out of the
raw signature.
"""

import ast
from dataclasses import dataclass, field


@dataclass
class FunctionInfo:
    name: str
    params: list[dict]
    return_type: str | None
    docstring: str | None
    lineno: int
    is_async: bool
    decorators: list[str] = field(default_factory=list)


def _extract_params(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[dict]:
    """Build the params list, matching positional defaults to the
    trailing args they belong to (defaults align to the END of args.args)."""
    args = node.args.args
    defaults = node.args.defaults
    num_no_default = len(args) - len(defaults)

    params = []
    for i, arg in enumerate(args):
        default = None
        default_index = i - num_no_default
        if default_index >= 0:
            default = ast.unparse(defaults[default_index])

        params.append(
            {
                "name": arg.arg,
                "type": ast.unparse(arg.annotation) if arg.annotation else None,
                "default": default,
            }
        )
    return params


def extract_functions(filepath: str) -> list[FunctionInfo]:
    """Parse filepath and return FunctionInfo for every public, top-level-
    walked function. Names starting with "_" are skipped. Raises
    SyntaxError (with the filename in the message) if the file can't be
    parsed. An empty file returns []."""
    with open(filepath) as f:
        source = f.read()

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise SyntaxError(f"Syntax error parsing {filepath}: {exc}") from exc

    functions = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("_"):
            continue

        functions.append(
            FunctionInfo(
                name=node.name,
                params=_extract_params(node),
                return_type=ast.unparse(node.returns) if node.returns else None,
                docstring=ast.get_docstring(node),
                lineno=node.lineno,
                is_async=isinstance(node, ast.AsyncFunctionDef),
                decorators=[ast.unparse(d) for d in node.decorator_list],
            )
        )
    return functions


def extract_module_docstring(filepath: str) -> str | None:
    """Return the module-level docstring, or None if absent."""
    with open(filepath) as f:
        source = f.read()

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise SyntaxError(f"Syntax error parsing {filepath}: {exc}") from exc

    return ast.get_docstring(tree)

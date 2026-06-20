"""Static analysis of Python source via the ast module.

extract_function_metadata() never executes the target file — it parses
the source into an AST, walks FunctionDef/AsyncFunctionDef nodes, and
pulls out names, parameter metadata, return type, docstrings, raw
source lines, and any exceptions raised in the function body. This
gives the LLM-backed generator structured, typed input instead of
having it regex the raw signature, and the `raises` list lets the
generated tests cover documented exception paths explicitly.
"""

import ast
import linecache
from dataclasses import dataclass, field


@dataclass
class FunctionMeta:
    name: str
    params: list[dict]
    return_type: str | None
    docstring: str | None
    source_lines: list[str] = field(default_factory=list)
    lineno: int = 0
    raises: list[str] = field(default_factory=list)


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


def _extract_raises(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    """Walk the function subtree for Raise nodes and collect exception names."""
    raises = []
    for child in ast.walk(node):
        if isinstance(child, ast.Raise) and child.exc is not None:
            if isinstance(child.exc, ast.Call):
                raises.append(ast.unparse(child.exc.func))
            elif isinstance(child.exc, ast.Name):
                raises.append(child.exc.id)
    return raises


def extract_function_metadata(filepath: str) -> list[FunctionMeta]:
    """Parse filepath and return FunctionMeta for every public, top-level
    function (and nested functions reachable via ast.walk). Names starting
    with "_" are skipped. Raises SyntaxError (with the filename in the
    message) if the file can't be parsed. A file with no public functions
    returns []."""
    with open(filepath) as f:
        source = f.read()

    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as exc:
        raise SyntaxError(f"Syntax error parsing {filepath}: {exc}") from exc

    # Ensure linecache has fresh content for this file (works for files
    # not yet imported, and avoids stale cached lines across test runs).
    linecache.checkcache(filepath)
    all_lines = linecache.getlines(filepath)
    if not all_lines:
        all_lines = source.splitlines(keepends=True)

    functions = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("_"):
            continue

        end_lineno = getattr(node, "end_lineno", node.lineno)
        source_lines = [
            line.rstrip("\n") for line in all_lines[node.lineno - 1 : end_lineno]
        ]

        functions.append(
            FunctionMeta(
                name=node.name,
                params=_extract_params(node),
                return_type=ast.unparse(node.returns) if node.returns else None,
                docstring=ast.get_docstring(node),
                source_lines=source_lines,
                lineno=node.lineno,
                raises=_extract_raises(node),
            )
        )
    return functions

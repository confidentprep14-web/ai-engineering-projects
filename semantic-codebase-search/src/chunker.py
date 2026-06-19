"""Chunking strategies for semantic codebase search.

ast_chunk_python() walks a Python file's AST and extracts one chunk per
top-level/class-level function, keyed on signature + docstring (not the
full body — the body is implementation detail, the signature + docstring
is what a programmer actually searches for).

heuristic_chunk() is the fallback for everything that isn't Python: fixed
line-count blocks. Good enough for YAML, shell scripts, JS, etc.

file_hash() backs incremental indexing: only files whose MD5 changed get
re-chunked and re-embedded.
"""

import ast
import hashlib


def file_hash(filepath: str) -> str:
    """Return the MD5 hex digest of a file's raw bytes.

    Raises FileNotFoundError if the file cannot be read (the default
    behavior of open() on a missing path already does this).
    """
    with open(filepath, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def ast_chunk_python(filepath: str) -> list[dict]:
    """Parse a Python file and return one chunk per top-level function.

    Each chunk is {"function_name", "file", "lineno", "end_lineno", "text"}.
    text is the function's signature line plus its docstring (if any) —
    never the full body. Nested functions and dunder methods are skipped.
    Files with syntax errors log a warning and return [].
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
    except OSError as exc:
        print(f"Warning: could not read {filepath}: {exc}")
        return []

    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as exc:
        print(f"Warning: syntax error in {filepath}: {exc}")
        return []

    source_lines = source.splitlines()
    chunks = []

    top_level_function_types = (ast.FunctionDef, ast.AsyncFunctionDef)

    def _walk_top_level(nodes):
        """Yield FunctionDef/AsyncFunctionDef nodes from module and class bodies only.

        Skips nested functions (functions defined inside other functions) by
        not recursing into FunctionDef/AsyncFunctionDef bodies.
        """
        for node in nodes:
            if isinstance(node, top_level_function_types):
                yield node
            elif isinstance(node, ast.ClassDef):
                yield from _walk_top_level(node.body)

    for node in _walk_top_level(tree.body):
        if node.name.startswith("__"):
            continue

        lineno = node.lineno
        end_lineno = getattr(node, "end_lineno", lineno)

        signature_line = source_lines[lineno - 1].strip() if lineno - 1 < len(source_lines) else ""
        docstring = ast.get_docstring(node) or ""
        text = f"{signature_line}\n{docstring}".strip()

        chunks.append(
            {
                "function_name": node.name,
                "file": filepath,
                "lineno": lineno,
                "end_lineno": end_lineno,
                "text": text,
            }
        )

    return chunks


def heuristic_chunk(filepath: str, chunk_size: int = 30) -> list[dict]:
    """Split a non-Python file into fixed-size line-count chunks.

    Each chunk is {"file", "lineno", "end_lineno", "text", "function_name"},
    with function_name following the chunk_<start_line> pattern.
    """
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    chunks = []
    for start in range(0, len(lines), chunk_size):
        end = min(start + chunk_size, len(lines))
        block_lines = lines[start:end]
        start_line = start + 1
        end_line = end

        chunks.append(
            {
                "file": filepath,
                "lineno": start_line,
                "end_lineno": end_line,
                "text": "".join(block_lines),
                "function_name": f"chunk_{start_line}",
            }
        )

    return chunks

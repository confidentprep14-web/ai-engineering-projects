# Build Guide — Code Documentation Generator

## Step 1 — AST extraction without executing code

The `ast` module lets you analyze Python without running it:

```python
import ast

with open(filepath) as f:
    source = f.read()

tree = ast.parse(source)

for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef):
        name = node.name
        return_type = ast.unparse(node.returns) if node.returns else None
        docstring = ast.get_docstring(node)
        params = [
            {
                "name": arg.arg,
                "type": ast.unparse(arg.annotation) if arg.annotation else None,
            }
            for arg in node.args.args
        ]
```

This is safer than `exec` or `importlib` — no side effects, no dependency installation required.

## Step 2 — The documentation prompt

System prompt:
```
You are a technical writer. Document this Python function in markdown.
Include: one-sentence description, parameters table (Name | Type | Description),
return value, and one short usage example.
Do not repeat the function signature verbatim.
Max {DOC_MAX_WORDS} words.
```

User content:
```
Function: {name}
Parameters: {params_formatted}
Return type: {return_type}
Existing docstring: {docstring or "none"}
```

## Step 3 — Quick reference table (no LLM)

Generate the quick reference table from metadata — no LLM call needed. This is the first thing a reader sees. It's derived from AST, so it's always accurate.

## Step 4 — Diff display

Use `difflib.unified_diff`. Color with `rich`: iterate diff lines, print additions in green, removals in red.

## Debugging tips

- If the LLM generates a code block but doesn't close it, count ``` occurrences — odd count = unclosed fence
- If type hints show as `None` when you expect a type, check that the file uses `from __future__ import annotations`; in that case `ast.unparse` may return string literals
- Test on your own `src/main.py` — dogfooding catches formatting issues quickly

## How to talk about this in an interview

**"Why AST instead of just reading the raw text?"**
> AST gives structured data: I can extract param names, types, defaults, and return types as typed fields, not strings I have to parse. The LLM gets structured input and produces structured output — no prompt hacking needed.

**"What's the LLM doing that you couldn't do without it?"**
> The prose description: "This function establishes a connection to a PostgreSQL database and returns a cursor." That sentence requires understanding what `host`, `port`, and the return type mean together. Regex or templates can't do that.

**"How do you handle existing docstrings?"**
> If there's a docstring longer than 50 words, I use it directly without an LLM call. This respects the developer's intent and saves cost. The LLM only fills gaps.

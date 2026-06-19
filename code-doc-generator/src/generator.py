"""LLM-backed documentation generation.

generate_function_doc() builds a structured prompt from FunctionInfo
metadata (name, params, types, defaults, return type, existing
docstring) and calls the LLM for prose. generate_module_readme()
assembles a full README: module docstring, per-function docs, and a
"Quick reference" table built straight from metadata with no LLM call
at all — that table is the first thing a reader sees and it has to be
accurate, so it's derived, not generated.
"""

import os

from ast_parser import FunctionInfo, extract_module_docstring
from llm import get_completion

EXISTING_DOCSTRING_WORD_THRESHOLD = 50


def _format_params(params: list[dict]) -> str:
    if not params:
        return "none"
    parts = []
    for p in params:
        type_str = p["type"] if p["type"] else "type unknown"
        default_str = f" = {p['default']}" if p["default"] is not None else ""
        parts.append(f"{p['name']}: {type_str}{default_str}")
    return ", ".join(parts)


def _close_unclosed_fence(text: str) -> str:
    """If the LLM response has an odd number of ``` fences, append a
    closing fence so the markdown doesn't bleed into the next section."""
    if text.count("```") % 2 != 0:
        text = text.rstrip() + "\n```"
    return text


def _build_prompt(func: FunctionInfo) -> str:
    return (
        f"Function: {func.name}\n"
        f"Parameters: {_format_params(func.params)}\n"
        f"Return type: {func.return_type if func.return_type else 'type unknown'}\n"
        f"Existing docstring: {func.docstring if func.docstring else 'none'}\n"
        f"Is async: {func.is_async}\n"
        f"Decorators: {', '.join(func.decorators) if func.decorators else 'none'}"
    )


def _build_system_prompt() -> str:
    max_words = os.environ.get("DOC_MAX_WORDS", "120")
    return (
        "You are a technical writer. Generate a concise markdown section for this "
        "Python function. Include: what it does, parameters table (Name | Type | "
        "Description), return value, and one usage example. Do not repeat the raw "
        f"signature verbatim. Max {max_words} words."
    )


def generate_function_doc(func: FunctionInfo) -> str:
    """Return a '### {name}' markdown section documenting func.

    If func already has a docstring longer than 50 words, that
    docstring is used directly (no LLM call) and marked
    "[from existing docstring]" — this respects developer intent and
    saves cost; the LLM only fills gaps.
    """
    if func.docstring and len(func.docstring.split()) > EXISTING_DOCSTRING_WORD_THRESHOLD:
        body = f"[from existing docstring]\n\n{func.docstring}"
    else:
        prompt = _build_prompt(func)
        system = _build_system_prompt()
        body = get_completion(prompt, system=system)
        body = _close_unclosed_fence(body)

    return f"### {func.name}\n\n{body}"


def _quick_reference_table(functions: list[FunctionInfo]) -> str:
    lines = ["## Quick reference", "", "| Function | Parameters | Returns |", "|---|---|---|"]
    for func in functions:
        params_str = _format_params(func.params)
        returns_str = func.return_type if func.return_type else "type unknown"
        lines.append(f"| {func.name} | {params_str} | {returns_str} |")
    return "\n".join(lines)


def generate_module_readme(filepath: str, functions: list[FunctionInfo]) -> str:
    """Assemble a full module README: '# <module_name>' heading, module
    docstring section (if present), one generate_function_doc() section
    per function, and a Quick reference table built from metadata.

    An empty functions list returns a minimal README stating no public
    functions were found.
    """
    module_name = os.path.splitext(os.path.basename(filepath))[0]
    sections = [f"# {module_name}"]

    module_docstring = extract_module_docstring(filepath)
    if module_docstring:
        sections.append(module_docstring)

    if not functions:
        sections.append("No public functions found.")
        return "\n\n".join(sections)

    for func in functions:
        sections.append(generate_function_doc(func))

    sections.append(_quick_reference_table(functions))

    return "\n\n".join(sections)

"""Tests for src/generator.py — LLM-backed doc generation and the
no-LLM quick reference table.

The LLM is mocked via pytest-mock in every test here (no network, no API
key needed) — these tests exercise the prompt-building / post-processing
/ formatting logic, not the provider integration. The real provider
integration lives in src/llm.py and is exercised by the live smoke test
described in the project README, not by this suite.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ast_parser import FunctionInfo  # noqa: E402
from generator import generate_function_doc, generate_module_readme  # noqa: E402

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
SAMPLE_MODULE = str(FIXTURES_DIR / "sample_module.py")


def _make_func(name="example_func", params=None, return_type="None", docstring=None) -> FunctionInfo:
    return FunctionInfo(
        name=name,
        params=params if params is not None else [{"name": "value", "type": "int", "default": None}],
        return_type=return_type,
        docstring=docstring,
        lineno=1,
        is_async=False,
        decorators=[],
    )


def test_generated_markdown_has_no_unclosed_code_fences(mocker):
    """Spec test 4: if the LLM returns a response with an unclosed code
    fence (odd ``` count), generate_function_doc must close it before
    returning. Output must also start with '### '."""
    mocker.patch(
        "generator.get_completion",
        return_value=(
            "This function does a thing.\n\n"
            "```python\n"
            "example_func(5)\n"
        ),
    )

    func = _make_func()
    doc = generate_function_doc(func)

    assert doc.count("```") % 2 == 0
    assert doc.startswith("### ")


def test_module_readme_has_quick_reference_table(mocker):
    """Spec test 5: generate_module_readme with 3 mock FunctionInfo
    objects must produce a '## Quick reference' section listing all 3
    function names."""
    mocker.patch("generator.get_completion", return_value="Mocked doc body.")

    functions = [
        _make_func(name="alpha", params=[{"name": "x", "type": "int", "default": None}], return_type="int"),
        _make_func(name="beta", params=[{"name": "y", "type": "str", "default": None}], return_type="str"),
        _make_func(name="gamma", params=[], return_type="None"),
    ]

    readme = generate_module_readme(SAMPLE_MODULE, functions)

    assert "## Quick reference" in readme
    assert "alpha" in readme
    assert "beta" in readme
    assert "gamma" in readme

"""Tests for src/ast_parser.py — function extraction via the ast module.

No LLM involved here at all: this is pure static analysis, so every
test is a plain assertion against parsed structure.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ast_parser import extract_functions  # noqa: E402

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
SAMPLE_MODULE = str(FIXTURES_DIR / "sample_module.py")


def test_extracts_correct_function_names_and_params():
    """Spec test 1: connect(host: str, port: int = 5432) -> None must be
    extracted with correct param names, types, and defaults."""
    functions = extract_functions(SAMPLE_MODULE)
    names = [f.name for f in functions]
    assert "connect" in names

    connect_func = next(f for f in functions if f.name == "connect")
    host_param = next(p for p in connect_func.params if p["name"] == "host")
    port_param = next(p for p in connect_func.params if p["name"] == "port")

    assert host_param["type"] == "str"
    assert host_param["default"] is None
    assert port_param["type"] == "int"
    assert port_param["default"] == "5432"


def test_private_functions_are_skipped():
    """Spec test 2: _internal_helper starts with an underscore and must
    never appear in extract_functions output."""
    functions = extract_functions(SAMPLE_MODULE)
    names = [f.name for f in functions]
    assert "_internal_helper" not in names


def test_type_hints_captured_correctly():
    """Spec test 3: process(data: list[str]) -> dict[str, int] must
    round-trip through ast.unparse with the exact container syntax."""
    functions = extract_functions(SAMPLE_MODULE)
    process_func = next(f for f in functions if f.name == "process")

    assert process_func.return_type == "dict[str, int]"
    data_param = next(p for p in process_func.params if p["name"] == "data")
    assert data_param["type"] == "list[str]"

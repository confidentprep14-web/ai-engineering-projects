"""Tests for src/generator.py — prompt construction and the retry loop.

get_completion is mocked here (this is the established exception: unit
tests mock the LLM boundary; the real CLI path calls a live provider).
"""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from generator import (  # noqa: E402
    build_generation_prompt,
    generate_tests_for_function,
)
from parser import FunctionMeta  # noqa: E402

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
SIMPLE_MATH = str(FIXTURES_DIR / "simple_math.py")

ADD_FUNC = FunctionMeta(
    name="add",
    params=[
        {"name": "a", "type": "int", "default": None},
        {"name": "b", "type": "int", "default": None},
    ],
    return_type="int",
    docstring="Return the sum of a and b.",
    source_lines=["def add(a: int, b: int) -> int:", "    return a + b"],
    lineno=4,
    raises=[],
)


def test_generation_prompt_includes_prior_error_when_provided():
    """Spec test 6: build_generation_prompt must surface the prior error
    text and instruct the model to fix it."""
    prompt = build_generation_prompt(ADD_FUNC, prior_error="AssertionError: expected 4, got 5")

    assert "AssertionError: expected 4, got 5" in prompt
    assert "Fix" in prompt


def test_generation_prompt_without_prior_error_omits_fix_instruction():
    prompt = build_generation_prompt(ADD_FUNC)

    assert "add" in prompt
    assert "AssertionError" not in prompt


@patch("generator.get_completion")
@patch("generator.run_pytest_on_generated")
def test_retry_injects_error_message_into_next_prompt(mock_run_pytest, mock_get_completion):
    """Spec test 2: when the first attempt fails, generate_tests_for_function
    must call get_completion a second time with the prior error baked into
    the new prompt — this is the self-correction loop."""
    mock_get_completion.side_effect = [
        "def test_add():\n    assert add(2, 2) == 5",  # attempt 1 (wrong)
        "def test_add():\n    assert add(2, 2) == 4",  # attempt 2 (fixed)
    ]
    mock_run_pytest.side_effect = [
        {"passed": False, "error": "AssertionError: assert 4 == 5", "output": ""},
        {"passed": True, "error": "", "output": ""},
    ]

    result = generate_tests_for_function(ADD_FUNC, SIMPLE_MATH, max_retries=3)

    assert mock_get_completion.call_count == 2
    second_call_prompt = mock_get_completion.call_args_list[1].args[0]
    assert "AssertionError: assert 4 == 5" in second_call_prompt
    assert result == "def test_add():\n    assert add(2, 2) == 4"

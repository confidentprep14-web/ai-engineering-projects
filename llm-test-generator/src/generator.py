"""Prompt construction and the self-correcting retry loop.

generate_tests_for_function() asks the LLM for pytest code, then hands
it to validate_and_retry() which actually runs the tests with pytest
(src/validator.py) and, on failure, feeds the error back into a new
prompt so the model can self-correct. The LLM never gets the final say
on whether its own code is right — pytest does.
"""

from llm import get_completion
from parser import FunctionMeta
from validator import run_pytest_on_generated

SYSTEM_PROMPT = (
    "You are an expert at writing pytest tests. "
    "Return only valid Python code, no explanation, no markdown."
)


def build_generation_prompt(func: FunctionMeta, prior_error: str = "") -> str:
    """Build the user prompt describing func for the LLM to generate
    pytest tests against. If prior_error is set, prepend a fix instruction
    with the error text so the model can self-correct on retry."""
    params_desc = ", ".join(
        f"{p['name']}: {p['type'] or 'Any'}" + (f" = {p['default']}" if p["default"] else "")
        for p in func.params
    )
    raises_desc = ", ".join(func.raises) if func.raises else "none documented"
    source = "\n".join(func.source_lines)

    body = (
        f"Function name: {func.name}\n"
        f"Parameters: {params_desc}\n"
        f"Return type: {func.return_type or 'None'}\n"
        f"Docstring: {func.docstring or '(none)'}\n"
        f"Exceptions raised: {raises_desc}\n\n"
        f"Source:\n{source}\n\n"
        "Generate pytest test cases. Use only stdlib. Import the function "
        "from its module. Return only valid Python code, no markdown fences."
    )

    if prior_error:
        body = f"The previous attempt produced this error. Fix it:\n\n{prior_error}\n\n" + body

    return body


def validate_and_retry(
    func: FunctionMeta, test_code: str, source_file: str, max_retries: int
) -> str | None:
    """Run test_code through real pytest; on failure, rebuild the prompt
    with the error injected and ask the LLM again. Logs
    'Retry N/{max_retries}: injecting error into prompt' on each retry.
    Returns the first passing test code, or None if all retries fail.
    """
    prior_error = ""
    current_code = test_code

    for attempt in range(max_retries):
        if attempt > 0:
            print(f"Retry {attempt}/{max_retries}: injecting error into prompt")
            new_prompt = build_generation_prompt(func, prior_error=prior_error)
            current_code = get_completion(new_prompt, system=SYSTEM_PROMPT)

        result = run_pytest_on_generated(current_code, source_file, func.name)
        if result["passed"]:
            return current_code
        prior_error = result["error"]

    return None


def generate_tests_for_function(
    func: FunctionMeta, source_module: str, max_retries: int = 3
) -> str | None:
    """End-to-end: build the first prompt, call the LLM, then validate
    and retry. Returns passing test code or None. Does not write files."""
    prompt = build_generation_prompt(func)
    test_code = get_completion(prompt, system=SYSTEM_PROMPT)
    return validate_and_retry(func, test_code, source_module, max_retries)

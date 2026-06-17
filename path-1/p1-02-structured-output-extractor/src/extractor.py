import json
import os

from pydantic import BaseModel, ValidationError

import llm

JSON_CODE_FENCE_MARKER = "```"


class ExtractionError(Exception):
    """Raised when the LLM still returns invalid JSON after all retry attempts."""


def strip_json_fences(raw: str) -> str:
    """Remove a leading/trailing markdown code fence (```` ```json ```` or ```` ``` ````)
    that LLMs commonly wrap JSON responses in, even when told not to.
    """
    cleaned_text = raw.strip()
    if cleaned_text.startswith(JSON_CODE_FENCE_MARKER):
        cleaned_text = cleaned_text[len(JSON_CODE_FENCE_MARKER):]
        if cleaned_text.startswith("json"):
            cleaned_text = cleaned_text[len("json"):]
        if cleaned_text.endswith(JSON_CODE_FENCE_MARKER):
            cleaned_text = cleaned_text[: -len(JSON_CODE_FENCE_MARKER)]
    return cleaned_text.strip()


def extract(
    text: str, schema_class: type[BaseModel], document_type: str
) -> tuple[BaseModel, int]:
    """Extract structured data from free text and validate it against schema_class.

    Retries up to MAX_RETRIES times, feeding the previous validation error back
    into the prompt so the LLM has a concrete reason to fix its next response.
    Returns (validated_object, attempts_used).
    """
    max_retries = int(os.environ.get("MAX_RETRIES", "3"))
    schema_json = schema_class.model_json_schema()
    system_prompt = (
        "You are a data extractor. Return ONLY valid JSON matching this schema. "
        f"No explanation, no markdown, no code fences. Schema: {schema_json}"
    )
    user_prompt = f"Extract structured data from this {document_type}:\n\n{text}"

    for attempt_number in range(1, max_retries + 1):
        raw_completion = llm.get_completion(user_prompt, system=system_prompt)
        cleaned_json_text = strip_json_fences(raw_completion)

        try:
            validated_object = schema_class.model_validate_json(cleaned_json_text)
            return validated_object, attempt_number
        except (json.JSONDecodeError, ValidationError) as validation_error:
            print(f"Attempt {attempt_number} failed: {validation_error}")
            user_prompt = (
                f"Extract structured data from this {document_type}:\n\n{text}\n\n"
                f"Previous attempt returned invalid JSON: {validation_error}. "
                "Fix it and return valid JSON only."
            )

    raise ExtractionError(f"Failed to extract after {max_retries} attempts")


def batch_extract(
    file_paths: list[str], schema_class: type[BaseModel], document_type: str
) -> dict:
    """Run extract() on every file in file_paths, tolerating per-file failures.

    Returns aggregate counts plus a per-file results list so the caller can
    print both a summary metric and individual outcomes.
    """
    extraction_successes = 0
    extraction_failures = 0
    total_llm_attempts = 0
    per_file_results = []

    for file_path in file_paths:
        with open(file_path, "r", encoding="utf-8") as input_file:
            document_text = input_file.read()

        try:
            validated_object, attempts_used = extract(document_text, schema_class, document_type)
            extraction_successes += 1
            total_llm_attempts += attempts_used
            per_file_results.append(
                {"file": file_path, "status": "success", "attempts": attempts_used}
            )
        except ExtractionError as extraction_error:
            extraction_failures += 1
            total_llm_attempts += int(os.environ.get("MAX_RETRIES", "3"))
            per_file_results.append(
                {"file": file_path, "status": "failure", "error": str(extraction_error)}
            )

    return {
        "successes": extraction_successes,
        "failures": extraction_failures,
        "total_attempts": total_llm_attempts,
        "results": per_file_results,
    }

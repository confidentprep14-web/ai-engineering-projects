import sys
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from extractor import ExtractionError, extract, strip_json_fences
from schemas.job_posting import JobPosting

VALID_JOB_POSTING_JSON = (
    '{"job_title": "Senior ML Engineer", "company_name": "Acme Corp", '
    '"location": "Remote", "employment_type": "Full-time", '
    '"required_skills": ["Python", "PyTorch"], '
    '"years_experience_required": 5, "salary_range": "$180k-$220k"}'
)

INCOMPLETE_JOB_POSTING_JSON = '{"job_title": "Engineer"}'


def test_clean_json_succeeds_on_first_attempt():
    with patch("extractor.llm.get_completion", return_value=VALID_JOB_POSTING_JSON) as mocked_completion:
        validated_object, attempts_used = extract(
            "some job posting text", JobPosting, "job posting"
        )

    assert isinstance(validated_object, JobPosting)
    assert validated_object.job_title == "Senior ML Engineer"
    assert attempts_used == 1
    assert mocked_completion.call_count == 1


def test_json_inside_code_fence_is_stripped():
    fenced_text = '```json\n{"a": 1}\n```'
    assert strip_json_fences(fenced_text) == '{"a": 1}'


def test_retry_on_malformed_json_then_success():
    with patch(
        "extractor.llm.get_completion",
        side_effect=["not json", VALID_JOB_POSTING_JSON],
    ) as mocked_completion:
        validated_object, attempts_used = extract(
            "some job posting text", JobPosting, "job posting"
        )

    assert isinstance(validated_object, JobPosting)
    assert attempts_used == 2
    assert mocked_completion.call_count == 2


def test_extraction_error_raised_after_max_retries(monkeypatch):
    monkeypatch.setenv("MAX_RETRIES", "3")
    with patch("extractor.llm.get_completion", return_value="not json") as mocked_completion:
        with pytest.raises(ExtractionError):
            extract("some job posting text", JobPosting, "job posting")

    assert mocked_completion.call_count == 3


def test_validation_error_triggers_retry():
    with patch(
        "extractor.llm.get_completion",
        side_effect=[INCOMPLETE_JOB_POSTING_JSON, VALID_JOB_POSTING_JSON],
    ) as mocked_completion:
        validated_object, attempts_used = extract(
            "some job posting text", JobPosting, "job posting"
        )

    assert isinstance(validated_object, JobPosting)
    assert attempts_used == 2
    assert mocked_completion.call_count == 2

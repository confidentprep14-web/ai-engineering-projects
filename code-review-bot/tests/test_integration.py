"""Integration test that makes a real LLM call against the hardcoded
secret fixture. Skipped automatically when ANTHROPIC_API_KEY is not set
so the suite never fails or hangs in an environment without credentials.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reviewer import review_chunk  # noqa: E402

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set — skipping real LLM integration test",
)
def test_known_issue_detection_hardcoded_secret():
    """Run the hardcoded_secret.py fixture through a real review_chunk
    call and assert at least one finding is flagged as security."""
    fixture_path = FIXTURES_DIR / "hardcoded_secret.py"
    source_code = fixture_path.read_text()

    synthetic_diff = (
        "diff --git a/tests/fixtures/hardcoded_secret.py b/tests/fixtures/hardcoded_secret.py\n"
        "index 0000000..1111111 100644\n"
        "--- a/tests/fixtures/hardcoded_secret.py\n"
        "+++ b/tests/fixtures/hardcoded_secret.py\n"
        "@@ -1,1 +1," + str(len(source_code.splitlines())) + " @@\n"
        + "\n".join(f"+{line}" for line in source_code.splitlines())
        + "\n"
    )

    chunk = {
        "filename": "tests/fixtures/hardcoded_secret.py",
        "diff": synthetic_diff,
        "lines": len(source_code.splitlines()),
    }

    findings = review_chunk(chunk, min_severity="LOW")

    assert any(finding.get("category") == "security" for finding in findings)

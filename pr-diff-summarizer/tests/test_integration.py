"""Integration test that makes a real LLM call against the with_tests
fixture. Skipped automatically when ANTHROPIC_API_KEY is not set so the
suite never fails or hangs in an environment without credentials.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from summarizer import generate_summary, parse_diff_stats  # noqa: E402

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set — skipping real LLM integration test",
)
def test_real_summary_is_plain_english_and_under_word_limit():
    """Run the with_tests.diff fixture through a real generate_summary
    call and assert the output respects the word limit and contains no
    raw diff lines."""
    diff_text = (FIXTURES_DIR / "with_tests.diff").read_text()
    stats = parse_diff_stats(diff_text)

    summary = generate_summary(diff_text, title="Add remember-me login", stats=stats)

    max_words = int(os.environ.get("SUMMARY_MAX_WORDS", "150"))
    assert len(summary.split()) <= max_words + 1  # +1 tolerance for trailing [...] marker
    for line in summary.splitlines():
        assert not line.startswith("+")
        assert not line.startswith("-")

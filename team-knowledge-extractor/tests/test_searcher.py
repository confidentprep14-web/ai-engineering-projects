"""Tests for src/searcher.py — keyword scoring and recency ranking.

No LLM call involved: this module is pure scoring/ranking logic over
already-extracted Decision objects.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from extractor import Decision  # noqa: E402
from searcher import rank_decisions, recency_score, score_keyword_match  # noqa: E402


def _decision(**overrides) -> Decision:
    defaults = dict(
        id="abc123def456",
        date="2024-01-15",
        decision="Default decision",
        rationale="Default rationale",
        author="someone",
        tags=["misc"],
        source_file="source.json",
        source_type="github_issue",
        raw_title="Default title",
    )
    defaults.update(overrides)
    return Decision(**defaults)


def test_keyword_search_returns_most_relevant_decision():
    """Spec test 1: rank_decisions('authentication oauth') must put the
    authentication-related decision first among auth/database/CI options."""
    auth_decision = _decision(
        decision="Adopt OAuth2 for authentication",
        rationale="OAuth2 access tokens reduce blast radius versus static API keys",
        tags=["authentication", "oauth", "security"],
        raw_title="Adopt OAuth2 client-credentials",
        source_file="issue_99.json",
    )
    db_decision = _decision(
        decision="Switch to PostgreSQL",
        rationale="PostgreSQL gives us JSONB with indexing",
        tags=["database", "postgresql"],
        raw_title="Switch to PostgreSQL for JSONB",
        source_file="issue_42.json",
    )
    ci_decision = _decision(
        decision="Move CI to GitHub Actions",
        rationale="Self-hosted CI was a maintenance burden",
        tags=["ci", "infrastructure"],
        raw_title="Move CI pipeline to GitHub Actions",
        source_file="0003-ci-pipeline.md",
    )

    results = rank_decisions("authentication oauth", [auth_decision, db_decision, ci_decision])

    assert results[0].source_file == "issue_99.json"


def test_recency_ranking_puts_newer_decisions_first():
    """Spec test 2: with recency_weight=1.0 (pure recency), a 2024 decision
    must outrank an otherwise-identical 2020 decision."""
    old_decision = _decision(date="2020-01-01", source_file="old.json")
    new_decision = _decision(date="2024-01-01", source_file="new.json")

    results = rank_decisions("", [old_decision, new_decision], recency_weight=1.0)

    assert results[0].source_file == "new.json"


def test_score_keyword_match_full_match_on_tag_gets_bonus():
    decision = _decision(
        decision="Adopt OAuth2 for authentication",
        rationale="Short-lived tokens",
        tags=["authentication", "oauth"],
        raw_title="Adopt OAuth2",
    )
    score = score_keyword_match("authentication", decision)
    assert 0.0 < score <= 1.0


def test_score_keyword_match_no_match_is_zero():
    decision = _decision(
        decision="Switch to PostgreSQL",
        rationale="JSONB support",
        tags=["database"],
        raw_title="Switch to PostgreSQL",
    )
    score = score_keyword_match("kubernetes helm chart", decision)
    assert score == 0.0


def test_recency_score_today_is_one():
    from datetime import date

    today_decision = _decision(date=date.today().isoformat())
    assert recency_score(today_decision) == 1.0


def test_recency_score_invalid_date_returns_neutral():
    decision = _decision(date="not-a-date")
    assert recency_score(decision) == 0.5

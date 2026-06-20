"""Keyword scoring and recency ranking — deliberately no embeddings.

Decisions are structured, well-labeled records (explicit tags, dates,
short summaries), so plain keyword + recency scoring is interpretable,
fast, and accurate enough. Embeddings are saved for the next project's
unstructured-document search.
"""

import math
from datetime import date, datetime

from extractor import Decision


def score_keyword_match(query: str, decision: Decision) -> float:
    """Score 0.0-1.0: fraction of query tokens found in the decision's
    text fields, with matched tags counted twice (2x bonus)."""
    tokens = query.lower().split()
    if not tokens:
        return 1.0

    tags_lower = [tag.lower() for tag in decision.tags]
    haystack = " ".join(
        [
            decision.decision or "",
            decision.rationale or "",
            decision.raw_title or "",
            " ".join(decision.tags),
        ]
    ).lower()

    matched = 0
    for token in tokens:
        in_text = token in haystack
        in_tag = token in tags_lower
        if in_tag:
            matched += 2
        elif in_text:
            matched += 1

    return min(1.0, matched / len(tokens))


def recency_score(decision: Decision) -> float:
    """Score 0.0-1.0: 1.0 for today, decaying logarithmically with age.
    Returns 0.5 (neutral) if decision.date is missing or unparseable."""
    if not decision.date:
        return 0.5

    try:
        decision_date = datetime.strptime(decision.date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return 0.5

    days_old = (date.today() - decision_date).days
    days_old = max(0, days_old)
    return 1.0 / (1.0 + math.log1p(days_old))


def rank_decisions(
    query: str,
    decisions: list[Decision],
    recency_weight: float = 0.3,
    top_k: int = 5,
) -> list[Decision]:
    """Rank decisions by combined keyword + recency score, descending."""
    scored = []
    for decision in decisions:
        keyword = score_keyword_match(query, decision)
        recency = recency_score(decision)
        combined = (1 - recency_weight) * keyword + recency_weight * recency
        scored.append((combined, decision))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [decision for _, decision in scored[:top_k]]

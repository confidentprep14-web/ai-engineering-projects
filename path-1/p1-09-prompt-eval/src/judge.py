"""LLM-as-judge scorer.

One judge call per scoring dimension (not one call for all dimensions) — this
avoids anchoring bias, where the judge's first score in a multi-score response
pulls the rest toward it. See GUIDE.md for the full rationale.
"""
import json
import os

from src import llm

JUDGE_PROMPT_TEMPLATE = """You are an objective evaluator. Score the following AI response on one dimension.

Dimension: {dimension_name}
Description: {dimension_description}

User question: {test_input}
Context provided to the AI: {context}
AI Response: {response}

Score 1-5 where:
1 = completely fails this dimension
3 = acceptable, meets minimum bar
5 = excellent, exceeds expectations

Return JSON: {{"score": N, "reasoning": "one sentence"}}"""


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def score_response(response: str, test_input: str, context: str, dimension: dict) -> dict:
    """Ask the judge model to score `response` on a single dimension.

    Returns {"score": int 1-5, "passed": bool, "reasoning": str}. On any
    parse failure, returns score=0/passed=False with a note in reasoning
    rather than raising, so one bad judge call doesn't kill the whole run.
    """
    judge_prompt = JUDGE_PROMPT_TEMPLATE.format(
        dimension_name=dimension["name"],
        dimension_description=dimension["description"],
        test_input=test_input,
        context=context,
        response=response,
    )

    judge_model = os.environ.get("JUDGE_MODEL") or None
    judge_provider = os.environ.get("JUDGE_PROVIDER") or None

    raw = llm.get_completion(
        judge_prompt,
        model_override=judge_model,
        provider_override=judge_provider,
    )

    try:
        cleaned = _strip_code_fences(raw)
        parsed = json.loads(cleaned)
        score = int(parsed["score"])
        reasoning = str(parsed["reasoning"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return {
            "score": 0,
            "passed": False,
            "reasoning": "Judge returned invalid JSON",
        }

    passed = score >= dimension["passing_threshold"]
    return {"score": score, "passed": passed, "reasoning": reasoning}

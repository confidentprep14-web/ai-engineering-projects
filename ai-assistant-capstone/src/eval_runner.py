"""LLM-as-judge eval runner for POST /eval.

Parses a suite.yaml-shaped dict, runs each test case through the same
chat_loop used by /chat (so the eval exercises the real RAG + tool + context
path, not a separate code path), and scores each response with an LLM judge
against the suite's scoring_dimensions. A judge failure marks that one test
case as failed without crashing the rest of the suite (see "Failure modes"
in GUIDE.md).
"""
from src.chat_loop import build_system_prompt, retrieval_hit, run_tool_loop
from src.config import config
from src.context import ContextManager
from src.llm import get_completion
from src.rag import format_rag_context, retrieve

JUDGE_PROMPT_TEMPLATE = """You are grading an AI assistant's response.

Question: {question}
Response: {response}

Scoring dimensions:
{dimensions}

For each dimension, give a score from 1-5. Then give an overall verdict of
PASS or FAIL (PASS if every dimension meets its passing threshold).
Respond with exactly this format:
{dimension_lines}
VERDICT: PASS|FAIL
"""


def _judge(question: str, response: str, scoring_dimensions: list[dict]) -> dict:
    dimensions_text = "\n".join(f"- {d['name']}: {d['description']} (pass >= {d['passing_threshold']})" for d in scoring_dimensions)
    dimension_lines = "\n".join(f"{d['name'].upper()}: <score>" for d in scoring_dimensions)
    prompt = JUDGE_PROMPT_TEMPLATE.format(
        question=question, response=response, dimensions=dimensions_text, dimension_lines=dimension_lines
    )

    try:
        judge_result = get_completion([{"role": "user", "content": prompt}])
        judge_text = judge_result["content"]
    except Exception as judge_error:
        return {"passed": False, "summary": f"Judge unavailable: {judge_error}"}

    passed = "VERDICT: PASS" in judge_text.upper()
    return {"passed": passed, "summary": judge_text.strip()[:300]}


def run_eval_suite(suite: dict, index, metadata, embedding_model) -> dict:
    """Run every test case in `suite` and return the results + summary dict."""
    results = []
    retrieval_hit_flags = []
    context_manager = ContextManager(config.max_context_tokens, config.context_strategy)

    for test_case in suite.get("test_cases", []):
        use_rag = bool(test_case.get("use_rag", False))
        question = test_case["input"]

        context_manager.add_message("user", question)

        chunks = []
        if use_rag:
            chunks = retrieve(question, index, metadata, embedding_model, config.rag_top_k, config.rag_score_threshold)
        system_prompt = build_system_prompt(format_rag_context(chunks))

        # A provider outage (or, in this build environment, no LLM_API_KEY at
        # all) must fail just this one test case, not the whole suite — same
        # "judge unavailable" precedent as _judge() below, extended to the
        # answer-generation call itself.
        try:
            run_tool_loop(context_manager, system_prompt)
            answer_completion = get_completion(context_manager.messages, system=system_prompt)
            answer_text = answer_completion["content"]
        except Exception as generation_error:
            results.append(
                {"id": test_case["id"], "passed": False, "summary": f"LLM unavailable: {generation_error}"}
            )
            continue

        context_manager.add_message("assistant", answer_text)

        hit = retrieval_hit(answer_text, chunks) if use_rag else False
        if use_rag:
            retrieval_hit_flags.append(hit)

        judge_verdict = _judge(question, answer_text, suite.get("scoring_dimensions", []))
        results.append({"id": test_case["id"], "passed": judge_verdict["passed"], "summary": judge_verdict["summary"]})

    passed_count = sum(1 for r in results if r["passed"])
    retrieval_hit_rate = (
        round(sum(retrieval_hit_flags) / len(retrieval_hit_flags), 4) if retrieval_hit_flags else None
    )

    return {
        "suite_name": suite.get("suite_name", "Unnamed suite"),
        "results": results,
        "summary": {
            "passed": passed_count,
            "total": len(results),
            "retrieval_hit_rate": retrieval_hit_rate,
        },
    }

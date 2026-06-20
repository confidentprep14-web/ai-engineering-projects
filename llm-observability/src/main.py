"""Demo script: instruments N LLM calls with LLMTracer and prints a
live-ish per-call log line followed by a final dashboard summary.

Requires a configured LLM_PROVIDER + matching API key (or a running
Ollama) — this is the one code path in this project that makes real
LLM calls; the test suite never exercises it.
"""

import argparse

from dotenv import load_dotenv

from tracer import LLMTracer

DEMO_PROMPTS = [
    "What is recursion?",
    "Explain a binary tree.",
    "What is a hash map?",
    "Describe the difference between a process and a thread.",
    "What is Big-O notation?",
]


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="LLM observability demo")
    parser.add_argument("--requests", type=int, default=20, help="Number of demo LLM calls to make")
    parser.add_argument("--prompt", type=str, default=None, help="Custom prompt to use for every call")
    args = parser.parse_args()

    tracer = LLMTracer()

    for i in range(1, args.requests + 1):
        prompt = args.prompt if args.prompt else DEMO_PROMPTS[(i - 1) % len(DEMO_PROMPTS)]

        before = dict(tracer.stats)
        _, trace_id = tracer.traced_completion(prompt)
        after = tracer.stats

        # traced_completion() only returns (text, trace_id) per spec;
        # per-call latency/tokens/cost are recovered as the delta in
        # accumulated stats rather than adding an undocumented return
        # value to the tracer's public contract.
        call_latency_ms = after["total_latency_ms"] - before["total_latency_ms"]
        call_tokens = after["total_tokens"] - before["total_tokens"]
        call_cost_usd = after["total_cost_usd"] - before["total_cost_usd"]

        print(
            f"[{i}/{args.requests}] trace_id={trace_id} | "
            f"latency={call_latency_ms}ms | tokens={call_tokens} | "
            f"cost=${call_cost_usd:.6f}"
        )

    tracer.print_dashboard()


if __name__ == "__main__":
    main()

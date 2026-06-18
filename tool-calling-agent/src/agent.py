"""The agentic loop: reason, call a tool, observe the result, reason again."""

import os
from dataclasses import dataclass, field

from llm import get_completion
from tools import call_tool, get_tool_schemas

SYSTEM_PROMPT = (
    "You are a helpful assistant with access to tools. To use a tool, respond with a tool call.\n"
    "When you have enough information to answer, give your final answer directly.\n"
    "Always show your reasoning before calling a tool."
)

DEFAULT_MAX_ITERATIONS = 8
TRACE_OUTPUT_PREVIEW_CHARS = 100


@dataclass
class AgentResult:
    question: str
    final_answer: str
    tools_used: list[str]
    iterations: int
    hit_max_iterations: bool
    trace: list[dict] = field(default_factory=list)


def run_agent(question: str, max_iterations: int = None) -> AgentResult:
    """Run the reason -> act -> observe loop until the LLM gives a final answer.

    The loop never raises on a tool failure: call_tool() always returns a
    string, even an error string, and that string is fed back to the LLM as
    context so it can recover (try a different tool, rephrase, give up
    gracefully). The only hard stop is the max-iterations guard, which exists
    so a confused LLM calling tools in circles cannot loop forever.
    """
    if max_iterations is None:
        max_iterations = int(os.environ.get("MAX_ITERATIONS", DEFAULT_MAX_ITERATIONS))

    conversation_messages = [{"role": "user", "content": question}]
    tools_used: list[str] = []
    reasoning_trace: list[dict] = []
    tool_schemas = get_tool_schemas()

    iteration_count = 0
    hit_max_iterations = False
    final_answer = ""

    while True:
        iteration_count += 1

        if iteration_count > max_iterations:
            hit_max_iterations = True
            final_answer = "Reached max iterations. Best answer with current info: " + final_answer
            break

        completion = get_completion(conversation_messages, system=SYSTEM_PROMPT, tools=tool_schemas)
        tool_call = completion["tool_call"]

        if tool_call is None:
            final_answer = completion["content"] or "(no answer produced)"
            reasoning_trace.append(
                {"iteration": iteration_count, "type": "answer", "tool": None, "input": None, "output": final_answer}
            )
            break

        tool_name = tool_call["tool_name"]
        tool_arguments = tool_call["arguments"]
        print(f"[Iter {iteration_count}] \U0001f527 Calling {tool_name}({tool_arguments})")

        tool_result = call_tool(tool_name, tool_arguments)
        print(f"         → {tool_result[:TRACE_OUTPUT_PREVIEW_CHARS]}")

        tools_used.append(tool_name)
        reasoning_trace.append(
            {
                "iteration": iteration_count,
                "type": "tool_call",
                "tool": tool_name,
                "input": str(tool_arguments),
                "output": tool_result,
            }
        )

        conversation_messages.append({"role": "assistant", "content": f"I'll use {tool_name}"})
        conversation_messages.append({"role": "user", "content": f"Tool result: {tool_result}"})

    return AgentResult(
        question=question,
        final_answer=final_answer,
        tools_used=tools_used,
        iterations=iteration_count if not hit_max_iterations else max_iterations,
        hit_max_iterations=hit_max_iterations,
        trace=reasoning_trace,
    )

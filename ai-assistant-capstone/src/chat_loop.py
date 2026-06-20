"""The /chat orchestration: RAG retrieval + context management + tool loop.

Split out of main.py to keep main.py under the 200-line cap and because this
is the one piece of real domain logic in the request path — worth testing
and reading on its own. run_chat_turn() does the non-streaming tool-calling
loop (reason -> call a tool -> observe -> repeat), then hands the final
no-tool-call turn to stream_completion() so the answer streams to the client
over SSE.
"""
from src.config import config
from src.context import ContextManager
from src.llm import get_completion, stream_completion
from src.rag import format_rag_context, retrieve
from src.tools import call_tool, get_tool_schemas

BASE_SYSTEM_PROMPT = (
    "You are a helpful AI assistant with access to tools and, when relevant context is "
    "provided, retrieved document excerpts. Use the provided context to answer questions "
    "about uploaded documents — cite it naturally. Use tools for arithmetic, the current "
    "date/time, or looking up facts on Wikipedia. When you have enough information, give "
    "your final answer directly as plain text."
)


def build_system_prompt(rag_context: str) -> str:
    if rag_context:
        return f"{BASE_SYSTEM_PROMPT}\n\n{rag_context}"
    return BASE_SYSTEM_PROMPT


def run_tool_loop(context_manager: ContextManager, system_prompt: str) -> tuple[list[str], int, int]:
    """Run get_completion in a loop, executing tool calls until a final answer.

    Returns (tools_used, prompt_tokens, completion_tokens) accumulated across
    every iteration that produced a tool call. The final no-tool-call
    iteration's tokens are NOT included here — that completion is discarded
    and the answer is re-generated via stream_completion() so the client
    sees it token-by-token instead of all at once.
    """
    tool_schemas = get_tool_schemas()
    tools_used: list[str] = []
    prompt_tokens_total = 0
    completion_tokens_total = 0

    for _ in range(config.max_tool_iterations):
        completion = get_completion(context_manager.messages, system=system_prompt, tools=tool_schemas)
        prompt_tokens_total += completion.get("prompt_tokens", 0)
        completion_tokens_total += completion.get("completion_tokens", 0)

        tool_call = completion["tool_call"]
        if tool_call is None:
            break

        tool_name = tool_call["tool_name"]
        tool_result = call_tool(tool_name, tool_call["arguments"])
        tools_used.append(tool_name)

        context_manager.add_message("assistant", f"I'll use {tool_name}")
        context_manager.add_message("user", f"Tool result: {tool_result}")

    return tools_used, prompt_tokens_total, completion_tokens_total


def retrieval_hit(answer_text: str, chunks: list[dict]) -> bool:
    """Heuristic: did the answer reference any retrieved chunk's content?

    Checks whether a contiguous 12+ character substring of any retrieved
    chunk appears in the answer. Cheap and conservative — false negatives
    (real use that doesn't match verbatim) are more likely than false
    positives, which is the safer direction for a "is RAG helping" metric.
    """
    if not chunks:
        return False
    answer_lower = answer_text.lower()
    for chunk in chunks:
        chunk_text_lower = chunk["text"].lower()
        window = 40
        for start in range(0, max(len(chunk_text_lower) - window, 0) + 1, window // 2):
            snippet = chunk_text_lower[start : start + window].strip()
            if len(snippet) >= 12 and snippet in answer_lower:
                return True
    return False


def run_chat_turn(message: str, history: list[dict], use_rag: bool, index, metadata, embedding_model):
    """Run one full /chat turn: RAG -> context -> tool loop -> stream answer.

    Returns (token_iterator, tools_used, chunks, context_manager) so main.py
    can drive the SSE response and log retrieval_hit/tool_used once the
    stream finishes.
    """
    context_manager = ContextManager(config.max_context_tokens, config.context_strategy)
    context_manager.load_messages(history)
    context_manager.add_message("user", message)
    context_manager.compress_if_needed(config.llm_model)

    chunks = []
    if use_rag:
        chunks = retrieve(message, index, metadata, embedding_model, config.rag_top_k, config.rag_score_threshold)
    system_prompt = build_system_prompt(format_rag_context(chunks))

    tools_used, _, _ = run_tool_loop(context_manager, system_prompt)

    token_iterator = stream_completion(context_manager.messages, system=system_prompt)
    return token_iterator, tools_used, chunks, context_manager

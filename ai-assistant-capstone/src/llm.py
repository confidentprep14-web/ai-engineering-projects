"""Provider-agnostic LLM wrapper: streaming + non-streaming, with tool-calling.

get_completion() is used by the tool-calling loop in main.py — it always
returns {"content": str, "tool_call": dict|None} regardless of provider, so
the loop never has to branch on LLM_PROVIDER (same pattern as the standalone
tool-calling-agent project).

stream_completion() is used for the final answer once the tool loop is done
(no more tool calls) — it yields (token_text, prompt_tokens, completion_tokens)
tuples, token counts populated only on the last yield, same pattern as the
streaming-chat-api / aws-lambda-deploy projects.

Ollama is intentionally not supported here: Lambda cannot run a local model
server, so this module only ever talks to a remote provider that reports its
own token usage and supports tool calling.
"""
import json
from typing import Iterator

from src.config import config


def format_tools_for_provider(tools: list[dict], provider: str) -> list[dict]:
    """Convert the internal tool schema into a provider-specific tool schema."""
    if provider == "anthropic":
        return [
            {
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool["parameters"],
            }
            for tool in tools
        ]
    if provider == "openai":
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"],
                },
            }
            for tool in tools
        ]
    raise ValueError(f"Unknown LLM_PROVIDER={provider!r}. Use anthropic or openai.")


def get_completion(messages: list[dict], system: str = "", tools: list[dict] | None = None) -> dict:
    """Send messages to the configured LLM provider and normalize the reply.

    Returns {"content": str, "tool_call": {"tool_name": str, "arguments": dict} | None,
    "prompt_tokens": int, "completion_tokens": int}.
    """
    tools = tools or []

    if config.llm_provider == "anthropic":
        return _complete_with_anthropic(messages, system, tools)
    if config.llm_provider == "openai":
        return _complete_with_openai(messages, system, tools)
    raise ValueError(f"Unknown LLM_PROVIDER={config.llm_provider!r}. Use anthropic or openai.")


def _complete_with_anthropic(messages: list[dict], system: str, tools: list[dict]) -> dict:
    import anthropic

    client = anthropic.Anthropic(api_key=config.llm_api_key)
    tools_schema = format_tools_for_provider(tools, "anthropic")

    completion_response = client.messages.create(
        model=config.llm_model,
        max_tokens=1024,
        system=system,
        messages=messages,
        tools=tools_schema if tools_schema else anthropic.NOT_GIVEN,
    )

    usage = {
        "prompt_tokens": completion_response.usage.input_tokens,
        "completion_tokens": completion_response.usage.output_tokens,
    }

    if completion_response.stop_reason == "tool_use":
        for content_block in completion_response.content:
            if content_block.type == "tool_use":
                return {
                    "content": "",
                    "tool_call": {"tool_name": content_block.name, "arguments": content_block.input},
                    **usage,
                }

    text_content = "".join(
        content_block.text for content_block in completion_response.content if content_block.type == "text"
    )
    return {"content": text_content, "tool_call": None, **usage}


def _complete_with_openai(messages: list[dict], system: str, tools: list[dict]) -> dict:
    import openai

    client = openai.OpenAI(api_key=config.llm_api_key)
    tools_schema = format_tools_for_provider(tools, "openai")

    openai_messages = []
    if system:
        openai_messages.append({"role": "system", "content": system})
    openai_messages.extend(messages)

    completion_response = client.chat.completions.create(
        model=config.llm_model,
        messages=openai_messages,
        tools=tools_schema if tools_schema else openai.NOT_GIVEN,
        tool_choice="auto" if tools_schema else openai.NOT_GIVEN,
    )
    response_message = completion_response.choices[0].message
    usage = {
        "prompt_tokens": completion_response.usage.prompt_tokens,
        "completion_tokens": completion_response.usage.completion_tokens,
    }

    if completion_response.choices[0].finish_reason == "tool_calls" and response_message.tool_calls:
        first_tool_call = response_message.tool_calls[0]
        return {
            "content": "",
            "tool_call": {
                "tool_name": first_tool_call.function.name,
                "arguments": json.loads(first_tool_call.function.arguments),
            },
            **usage,
        }

    return {"content": response_message.content or "", "tool_call": None, **usage}


def stream_completion(
    messages: list[dict], system: str = "", tools: list[dict] | None = None
) -> Iterator[tuple[str, int, int]]:
    """Stream the final answer once the tool-calling loop has no more tool calls.

    Yields (token_text, prompt_tokens, completion_tokens). Token counts are 0
    on every yield except the last, where real usage numbers are attached so
    the caller can log cost once the stream finishes.
    """
    if config.llm_provider == "anthropic":
        yield from _stream_anthropic(messages, system, tools or [])
    elif config.llm_provider == "openai":
        yield from _stream_openai(messages, system, tools or [])
    else:
        raise ValueError(f"Unknown LLM_PROVIDER={config.llm_provider!r}. Use anthropic or openai.")


def _stream_anthropic(messages: list[dict], system: str, tools: list[dict]) -> Iterator[tuple[str, int, int]]:
    import anthropic

    client = anthropic.Anthropic(api_key=config.llm_api_key)
    with client.messages.stream(
        model=config.llm_model,
        max_tokens=1024,
        system=system,
        messages=messages,
    ) as stream:
        for text_delta in stream.text_stream:
            yield text_delta, 0, 0
        final_message = stream.get_final_message()
        yield "", final_message.usage.input_tokens, final_message.usage.output_tokens


def _stream_openai(messages: list[dict], system: str, tools: list[dict]) -> Iterator[tuple[str, int, int]]:
    import openai

    client = openai.OpenAI(api_key=config.llm_api_key)
    openai_messages = []
    if system:
        openai_messages.append({"role": "system", "content": system})
    openai_messages.extend(messages)

    completion_chunks = client.chat.completions.create(
        model=config.llm_model,
        messages=openai_messages,
        stream=True,
        stream_options={"include_usage": True},
    )
    prompt_tokens = 0
    completion_tokens = 0
    for chunk in completion_chunks:
        if chunk.usage is not None:
            prompt_tokens = chunk.usage.prompt_tokens
            completion_tokens = chunk.usage.completion_tokens
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content, 0, 0
    yield "", prompt_tokens, completion_tokens

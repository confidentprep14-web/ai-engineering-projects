"""Provider-agnostic LLM wrapper with tool-calling support.

get_completion() always returns {"content": str, "tool_call": dict | None}
regardless of which provider answered, so agent.py never has to branch on
LLM_PROVIDER.
"""

import json
import os


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
    # ollama has no native tool-calling guarantee — tools are described in
    # the system prompt instead, so the raw internal schema is returned as-is.
    return tools


def get_completion(messages: list[dict], system: str = "", tools: list[dict] = None) -> dict:
    """Send messages to the configured LLM provider and normalize the reply.

    Returns {"content": str, "tool_call": {"tool_name": str, "arguments": dict} | None}.
    """
    llm_provider = os.environ.get("LLM_PROVIDER", "anthropic")
    llm_model = os.environ.get("LLM_MODEL", "")
    llm_api_key = os.environ.get("LLM_API_KEY", "")
    tools = tools or []

    if llm_provider == "anthropic":
        return _complete_with_anthropic(messages, system, llm_model, llm_api_key, tools)
    if llm_provider == "openai":
        return _complete_with_openai(messages, system, llm_model, llm_api_key, tools)
    if llm_provider == "ollama":
        return _complete_with_ollama(messages, system, llm_model, tools)
    raise ValueError(f"Unknown LLM_PROVIDER={llm_provider!r}. Use anthropic, openai, or ollama.")


def _complete_with_anthropic(messages, system, model, api_key, tools) -> dict:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    tools_schema = format_tools_for_provider(tools, "anthropic")

    completion_response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=system,
        messages=messages,
        tools=tools_schema if tools_schema else anthropic.NOT_GIVEN,
    )

    if completion_response.stop_reason == "tool_use":
        for content_block in completion_response.content:
            if content_block.type == "tool_use":
                return {
                    "content": "",
                    "tool_call": {"tool_name": content_block.name, "arguments": content_block.input},
                }

    text_content = "".join(
        content_block.text for content_block in completion_response.content if content_block.type == "text"
    )
    return {"content": text_content, "tool_call": None}


def _complete_with_openai(messages, system, model, api_key, tools) -> dict:
    import openai

    client = openai.OpenAI(api_key=api_key)
    tools_schema = format_tools_for_provider(tools, "openai")

    openai_messages = []
    if system:
        openai_messages.append({"role": "system", "content": system})
    openai_messages.extend(messages)

    completion_response = client.chat.completions.create(
        model=model,
        messages=openai_messages,
        tools=tools_schema if tools_schema else openai.NOT_GIVEN,
        tool_choice="auto" if tools_schema else openai.NOT_GIVEN,
    )
    response_message = completion_response.choices[0].message

    if completion_response.choices[0].finish_reason == "tool_calls" and response_message.tool_calls:
        first_tool_call = response_message.tool_calls[0]
        return {
            "content": "",
            "tool_call": {
                "tool_name": first_tool_call.function.name,
                "arguments": json.loads(first_tool_call.function.arguments),
            },
        }

    return {"content": response_message.content or "", "tool_call": None}


def _complete_with_ollama(messages, system, model, tools) -> dict:
    import ollama

    tool_descriptions = "\n".join(
        f"- {tool['name']}({tool['parameters'].get('properties', {})}): {tool['description']}" for tool in tools
    )
    tool_calling_instructions = (
        "If you need a tool, respond with ONLY a JSON object: "
        '{"tool": "<tool_name>", "args": {...}}. '
        "Otherwise respond with plain text.\n\nAvailable tools:\n" + tool_descriptions
        if tools
        else ""
    )
    combined_system_prompt = f"{system}\n\n{tool_calling_instructions}".strip()

    ollama_messages = []
    if combined_system_prompt:
        ollama_messages.append({"role": "system", "content": combined_system_prompt})
    ollama_messages.extend(messages)

    completion_response = ollama.chat(model=model, messages=ollama_messages)
    raw_reply = completion_response["message"]["content"]

    parsed_tool_call = _parse_ollama_tool_call(raw_reply)
    if parsed_tool_call is not None:
        return {"content": "", "tool_call": parsed_tool_call}
    return {"content": raw_reply, "tool_call": None}


def _parse_ollama_tool_call(raw_reply: str) -> dict | None:
    """Detect a fallback JSON tool call in an Ollama model's plain-text reply."""
    stripped_reply = raw_reply.strip()
    if not (stripped_reply.startswith("{") and stripped_reply.endswith("}")):
        return None
    try:
        parsed_json = json.loads(stripped_reply)
    except json.JSONDecodeError:
        return None
    if "tool" not in parsed_json:
        return None
    return {"tool_name": parsed_json["tool"], "arguments": parsed_json.get("args", {})}

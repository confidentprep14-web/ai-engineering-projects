import os


def get_completion(messages: list[dict], system: str = "") -> str:
    """Send a multi-turn completion request to the configured LLM provider.

    Takes the full conversation as a list of {"role", "content"} dicts so the
    context manager controls exactly what gets sent on every call.
    """
    llm_provider = os.environ.get("LLM_PROVIDER", "anthropic")
    llm_model = os.environ.get("LLM_MODEL", "")
    llm_api_key = os.environ.get("LLM_API_KEY", "")

    if llm_provider == "anthropic":
        return _complete_with_anthropic(messages, system, llm_model, llm_api_key)
    elif llm_provider == "openai":
        return _complete_with_openai(messages, system, llm_model, llm_api_key)
    elif llm_provider == "ollama":
        return _complete_with_ollama(messages, system, llm_model)
    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER={llm_provider!r}. Use anthropic, openai, or ollama."
        )


def _complete_with_anthropic(messages: list[dict], system: str, model: str, api_key: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    completion_response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=system,
        messages=messages,
    )
    return completion_response.content[0].text


def _complete_with_openai(messages: list[dict], system: str, model: str, api_key: str) -> str:
    import openai

    client = openai.OpenAI(api_key=api_key)
    full_messages = list(messages)
    if system:
        full_messages = [{"role": "system", "content": system}] + full_messages

    completion_response = client.chat.completions.create(model=model, messages=full_messages)
    return completion_response.choices[0].message.content


def _complete_with_ollama(messages: list[dict], system: str, model: str) -> str:
    import ollama

    full_messages = list(messages)
    if system:
        full_messages = [{"role": "system", "content": system}] + full_messages

    completion_response = ollama.chat(model=model, messages=full_messages)
    return completion_response["message"]["content"]

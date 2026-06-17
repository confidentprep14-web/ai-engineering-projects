import os


def get_completion(prompt: str, system: str = "") -> str:
    """Send one non-streaming completion request to the configured LLM provider.

    Provider, model, and API key are read from environment variables so the
    extraction logic in extractor.py never has to know which provider is active.
    """
    llm_provider = os.environ.get("LLM_PROVIDER", "anthropic")
    llm_model = os.environ.get("LLM_MODEL", "")
    llm_api_key = os.environ.get("LLM_API_KEY", "")

    if llm_provider == "anthropic":
        return _complete_with_anthropic(prompt, system, llm_model, llm_api_key)
    elif llm_provider == "openai":
        return _complete_with_openai(prompt, system, llm_model, llm_api_key)
    elif llm_provider == "ollama":
        return _complete_with_ollama(prompt, system, llm_model)
    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER={llm_provider!r}. Use anthropic, openai, or ollama."
        )


def _complete_with_anthropic(prompt: str, system: str, model: str, api_key: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    completion_response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return completion_response.content[0].text


def _complete_with_openai(prompt: str, system: str, model: str, api_key: str) -> str:
    import openai

    client = openai.OpenAI(api_key=api_key)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    completion_response = client.chat.completions.create(model=model, messages=messages)
    return completion_response.choices[0].message.content


def _complete_with_ollama(prompt: str, system: str, model: str) -> str:
    import ollama

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    completion_response = ollama.chat(model=model, messages=messages)
    return completion_response["message"]["content"]

import os


def get_completion(prompt: str, system: str = "") -> str:
    provider = os.environ.get("LLM_PROVIDER", "anthropic")
    model = os.environ.get("LLM_MODEL", "")
    api_key = os.environ.get("LLM_API_KEY", "")

    if provider == "anthropic":
        return _complete_anthropic(prompt, system, model, api_key)
    elif provider == "openai":
        return _complete_openai(prompt, system, model, api_key)
    elif provider == "ollama":
        return _complete_ollama(prompt, system, model)
    else:
        raise ValueError(f"Unknown LLM_PROVIDER={provider}. Use anthropic, openai, or ollama")


def _complete_anthropic(prompt: str, system: str, model: str, api_key: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    try:
        completion_response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in completion_response.content)
    except anthropic.APITimeoutError:
        print("LLM timeout — try again or check API status")
        raise


def _complete_openai(prompt: str, system: str, model: str, api_key: str) -> str:
    import openai

    client = openai.OpenAI(api_key=api_key)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        completion_response = client.chat.completions.create(model=model, messages=messages)
        return completion_response.choices[0].message.content or ""
    except openai.APITimeoutError:
        print("LLM timeout — try again or check API status")
        raise


def _complete_ollama(prompt: str, system: str, model: str) -> str:
    import ollama

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    completion_response = ollama.chat(model=model, messages=messages)
    return completion_response["message"]["content"]

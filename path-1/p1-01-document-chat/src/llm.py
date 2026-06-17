import os
from typing import Iterator


def stream_completion(prompt: str, system: str = "") -> Iterator[str]:
    provider = os.environ.get("LLM_PROVIDER", "anthropic")
    model = os.environ.get("LLM_MODEL", "")
    api_key = os.environ.get("LLM_API_KEY", "")

    if provider == "anthropic":
        yield from _stream_anthropic(prompt, system, model, api_key)
    elif provider == "openai":
        yield from _stream_openai(prompt, system, model, api_key)
    elif provider == "ollama":
        yield from _stream_ollama(prompt, system, model)
    else:
        raise ValueError(f"Unknown LLM_PROVIDER={provider}. Use anthropic, openai, or ollama")


def get_completion(prompt: str, system: str = "") -> str:
    return "".join(stream_completion(prompt, system))


def _stream_anthropic(prompt: str, system: str, model: str, api_key: str) -> Iterator[str]:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    try:
        with client.messages.stream(
            model=model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            yield from stream.text_stream
    except anthropic.APITimeoutError:
        print("LLM timeout — retry or reduce chunk count")
        raise


def _stream_openai(prompt: str, system: str, model: str, api_key: str) -> Iterator[str]:
    import openai

    client = openai.OpenAI(api_key=api_key)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        stream = client.chat.completions.create(model=model, messages=messages, stream=True)
        for chunk in stream:
            content = chunk.choices[0].delta.content
            if content is not None:
                yield content
    except openai.APITimeoutError:
        print("LLM timeout — retry or reduce chunk count")
        raise


def _stream_ollama(prompt: str, system: str, model: str) -> Iterator[str]:
    import ollama

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    for chunk in ollama.chat(model=model, messages=messages, stream=True):
        content = chunk["message"]["content"]
        if content:
            yield content

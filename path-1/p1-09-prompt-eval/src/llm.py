"""Provider-agnostic LLM wrapper.

get_completion() is the single entry point used both for generating test-case
responses and for running the judge. Env vars set the defaults; callers (the
judge, in particular) can override provider/model per call so generation and
judging can use different models.
"""
import os

from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def get_completion(
    prompt: str,
    system: str = "",
    model_override: str = None,
    provider_override: str = None,
) -> str:
    """Route a single-turn completion request to the configured provider.

    Raises ValueError if the resolved provider is unknown, and RuntimeError
    if no API key is configured for a provider that requires one.
    """
    provider = provider_override or _env("LLM_PROVIDER", "anthropic")
    model = model_override or _env("LLM_MODEL", "claude-3-5-haiku-20241022")

    if provider == "anthropic":
        return _complete_anthropic(prompt, system, model)
    elif provider == "openai":
        return _complete_openai(prompt, system, model)
    elif provider == "ollama":
        return _complete_ollama(prompt, system, model)
    else:
        raise ValueError(f"Unknown LLM provider: {provider!r}")


def _complete_anthropic(prompt: str, system: str, model: str) -> str:
    import anthropic

    api_key = _env("LLM_API_KEY")
    if not api_key:
        raise RuntimeError(
            "LLM_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in message.content if block.type == "text")


def _complete_openai(prompt: str, system: str, model: str) -> str:
    import openai

    api_key = _env("LLM_API_KEY")
    if not api_key:
        raise RuntimeError(
            "LLM_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    client = openai.OpenAI(api_key=api_key)
    messages = [{"role": "user", "content": prompt}]
    if system:
        messages = [{"role": "system", "content": system}] + messages
    completion = client.chat.completions.create(model=model, messages=messages)
    return completion.choices[0].message.content


def _complete_ollama(prompt: str, system: str, model: str) -> str:
    import ollama

    messages = [{"role": "user", "content": prompt}]
    if system:
        messages = [{"role": "system", "content": system}] + messages
    response = ollama.chat(model=model, messages=messages)
    return response["message"]["content"]

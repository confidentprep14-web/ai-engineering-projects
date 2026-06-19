"""Provider-agnostic LLM wrapper.

get_completion() reads LLM_PROVIDER/LLM_MODEL from the environment and
routes to Anthropic, OpenAI, or Ollama. Callers (summarizer.py) never
branch on the provider — they just call get_completion().

Unlike code-review-bot's llm.py, this module returns plain prose: no
JSON-mode instruction is appended and no JSON parsing happens here. The
summarizer needs natural-language paragraphs (summary, architecture
impact), not structured output.
"""

import json
import os


def get_completion(prompt: str, system: str = "") -> str:
    """Send a prompt to the configured LLM provider and return raw text."""
    provider = os.environ.get("LLM_PROVIDER", "anthropic")
    model = os.environ.get("LLM_MODEL", "")

    if provider == "anthropic":
        return _complete_with_anthropic(prompt, system, model)
    if provider == "openai":
        return _complete_with_openai(prompt, system, model)
    if provider == "ollama":
        return _complete_with_ollama(prompt, system, model)
    raise RuntimeError(f"Unknown LLM_PROVIDER={provider!r}. Use anthropic, openai, or ollama.")


def _complete_with_anthropic(prompt: str, system: str, model: str) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def _complete_with_openai(prompt: str, system: str, model: str) -> str:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    import openai

    client = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content or ""


def _complete_with_ollama(prompt: str, system: str, model: str) -> str:
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

    import urllib.error
    import urllib.request

    payload = json.dumps(
        {
            "model": model,
            "system": system,
            "prompt": prompt,
            "stream": False,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, ConnectionError) as exc:
        raise ConnectionError(f"Could not reach Ollama at {base_url}") from exc
    return body.get("response", "")

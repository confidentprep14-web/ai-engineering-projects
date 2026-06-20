"""Provider-agnostic LLM wrapper.

get_completion() reads LLM_PROVIDER/LLM_MODEL from the environment and
routes to Anthropic, OpenAI, or Ollama. This is the only module allowed
to call os.environ.get() on the API key secrets — tracer.py never
touches them directly, it just calls get_completion(). Unit tests mock
this function directly; it is never mocked in the main CLI code path.

Unlike a plain completion wrapper, this version returns usage data
alongside the text — (response_text, usage_dict) — since the tracer
needs token counts to compute latency-independent metrics like cost.
"""

import json
import os


def get_completion(prompt: str, system: str = "") -> tuple[str, dict]:
    """Send a prompt to the configured LLM provider.

    Returns (response_text, usage_dict) where usage_dict has
    "input_tokens" and "output_tokens" keys.

    Raises RuntimeError if the provider's required API key is missing,
    or if LLM_PROVIDER is set to something unrecognized.
    """
    provider = os.environ.get("LLM_PROVIDER", "anthropic")
    model = os.environ.get("LLM_MODEL", "")

    if provider == "anthropic":
        return _complete_with_anthropic(prompt, system, model)
    if provider == "openai":
        return _complete_with_openai(prompt, system, model)
    if provider == "ollama":
        return _complete_with_ollama(prompt, system, model)
    raise RuntimeError(f"Unknown LLM_PROVIDER={provider!r}. Use anthropic, openai, or ollama.")


def _complete_with_anthropic(prompt: str, system: str, model: str) -> tuple[str, dict]:
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
    text = "".join(block.text for block in response.content if block.type == "text")
    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }
    return text, usage


def _complete_with_openai(prompt: str, system: str, model: str) -> tuple[str, dict]:
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
    text = response.choices[0].message.content or ""
    usage = {
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
    }
    return text, usage


def _complete_with_ollama(prompt: str, system: str, model: str) -> tuple[str, dict]:
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

    text = body.get("response", "")
    # Ollama's /api/generate response includes prompt_eval_count and
    # eval_count when available; fall back to a word-count estimate.
    if "prompt_eval_count" in body and "eval_count" in body:
        usage = {"input_tokens": body["prompt_eval_count"], "output_tokens": body["eval_count"]}
    else:
        usage = {"input_tokens": len(prompt.split()), "output_tokens": len(text.split())}
    return text, usage

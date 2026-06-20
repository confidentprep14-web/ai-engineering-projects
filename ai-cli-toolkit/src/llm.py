"""Provider-agnostic LLM wrapper, shared by every tool in tools/.

get_completion() reads LLM_PROVIDER/LLM_MODEL from the environment and
routes to Anthropic, OpenAI, or Ollama. Tools never branch on the
provider — they just call get_completion()/get_json_completion(). This
is the only module allowed to call os.environ.get() on the API key
secrets. No mocked LLM calls in the main CLI code path — review.py,
explain.py, and query.py all call through to this module for real.
"""

import json
import os

JSON_MODE_INSTRUCTION = (
    "\n\nRespond with ONLY valid JSON. Do not include any prose, "
    "explanation, or markdown code fences — return the raw JSON only."
)


def get_completion(prompt: str, system: str = "") -> str:
    """Send a prompt to the configured LLM provider and return raw text.

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


def get_json_completion(prompt: str, system: str = "") -> dict | list:
    """Call get_completion with a JSON-mode system prompt and parse the result.

    Strips ```json ... ``` (or plain ``` ... ```) code fences if the model
    wrapped its response in markdown. Raises ValueError with the raw text
    if parsing still fails, so callers can log/handle it.
    """
    json_system = f"{system}{JSON_MODE_INSTRUCTION}" if system else JSON_MODE_INSTRUCTION.strip()
    raw_text = get_completion(prompt, json_system)
    cleaned_text = _strip_code_fences(raw_text)
    try:
        return json.loads(cleaned_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse JSON from LLM response: {raw_text!r}") from exc


def _strip_code_fences(text: str) -> str:
    """Remove a leading/trailing markdown code fence, if present."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()

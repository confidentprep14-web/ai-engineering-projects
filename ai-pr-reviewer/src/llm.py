"""Provider-agnostic LLM wrapper for the AI PR Reviewer action.

get_completion() reads LLM_PROVIDER/LLM_MODEL from the environment and
routes to Anthropic, OpenAI, or Ollama. Unlike the plain code-review-bot
version, this returns (response_text, usage_dict) so cost_tracker.py can
record token counts per call. Callers (action_runner.py) never branch on
provider — they just call get_completion()/get_json_completion().
"""

import json
import os

JSON_MODE_INSTRUCTION = (
    "\n\nRespond with ONLY valid JSON. Do not include any prose, "
    "explanation, or markdown code fences — return the raw JSON only."
)


def get_completion(prompt: str, system: str = "") -> tuple[str, dict]:
    """Send a prompt to the configured LLM provider.

    Returns (response_text, usage_dict) where
    usage_dict = {"input_tokens": int, "output_tokens": int}.
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
        "input_tokens": getattr(response.usage, "input_tokens", 0),
        "output_tokens": getattr(response.usage, "output_tokens", 0),
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
    usage = response.usage
    usage_dict = {
        "input_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
        "output_tokens": getattr(usage, "completion_tokens", 0) if usage else 0,
    }
    return text, usage_dict


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
    # Ollama reports token counts as prompt_eval_count / eval_count.
    usage = {
        "input_tokens": body.get("prompt_eval_count", 0),
        "output_tokens": body.get("eval_count", 0),
    }
    return text, usage


def get_json_completion(prompt: str, system: str = "") -> tuple[dict | list, dict]:
    """Call get_completion and parse the result as JSON.

    Returns (parsed_json, usage_dict). Strips ```json ... ``` (or plain
    ``` ... ```) code fences if the model wrapped its response in
    markdown. Raises ValueError with the raw text if parsing still fails,
    so callers can log/handle it.
    """
    json_system = f"{system}{JSON_MODE_INSTRUCTION}" if system else JSON_MODE_INSTRUCTION.strip()
    raw_text, usage = get_completion(prompt, json_system)
    cleaned_text = _strip_code_fences(raw_text)
    try:
        return json.loads(cleaned_text), usage
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

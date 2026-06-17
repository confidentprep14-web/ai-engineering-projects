import json
import os
import urllib.parse

import requests

from llm import get_completion

WIKIPEDIA_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{entity}"
# Wikimedia rejects requests without a descriptive User-Agent (HTTP 403) per
# https://meta.wikimedia.org/wiki/User-Agent_policy
WIKIPEDIA_USER_AGENT = "p1-05-multi-step-llm-pipeline/1.0 (https://github.com/; educational project)"


class StageError(Exception):
    """Raised when a pipeline stage cannot produce a usable result."""

    def __init__(self, stage_name: str, reason: str):
        self.stage_name = stage_name
        self.reason = reason
        super().__init__(f"Stage '{stage_name}' failed: {reason}")


def extract_entities(topic: str) -> list[str]:
    """Stage 1: ask the LLM for the named entities central to a topic.

    Returns a deduplicated list of entity name strings, preserving first-seen
    order. Raises StageError if the LLM response cannot be parsed as a JSON
    array of strings, or if extraction yields no entities at all.
    """
    max_entities = os.environ.get("MAX_ENTITIES", "5")
    system_prompt = (
        "Extract named entities from the input. Return ONLY a JSON array of "
        "strings. Include people, organisations, technologies, places, and "
        f"concepts central to the topic. Maximum {max_entities} items."
    )
    user_prompt = f"Topic: {topic}"

    raw_completion = get_completion(user_prompt, system=system_prompt)
    cleaned_completion = _strip_json_fences(raw_completion)

    try:
        parsed_entities = json.loads(cleaned_completion)
    except json.JSONDecodeError as parse_error:
        raise StageError("entity extraction", f"JSON parse failed: {parse_error}")

    if not isinstance(parsed_entities, list) or not all(
        isinstance(entity, str) for entity in parsed_entities
    ):
        raise StageError("entity extraction", "LLM response was not a JSON array of strings")

    deduplicated_entities = list(dict.fromkeys(parsed_entities))
    if not deduplicated_entities:
        raise StageError("entity extraction", "LLM returned empty entity list")

    return deduplicated_entities


def _strip_json_fences(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` fences some LLMs wrap arrays in."""
    stripped_text = text.strip()
    if stripped_text.startswith("```"):
        lines = stripped_text.splitlines()
        lines = lines[1:] if lines else lines
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped_text = "\n".join(lines).strip()
    return stripped_text


def fetch_entity_summaries(entities: list[str]) -> list[dict]:
    """Stage 2: fetch a Wikipedia summary for each entity over HTTP.

    Never raises on a per-entity failure (404, timeout, network error) —
    those are recorded as found=False so one bad entity doesn't sink the
    whole pipeline run.
    """
    timeout_seconds = float(os.environ.get("WIKIPEDIA_TIMEOUT_SECONDS", 5))
    entity_summaries = []

    for entity_name in entities:
        entity_summaries.append(_fetch_one_summary(entity_name, timeout_seconds))

    return entity_summaries


def _fetch_one_summary(entity_name: str, timeout_seconds: float) -> dict:
    encoded_entity = urllib.parse.quote(entity_name.replace(" ", "_"))
    summary_url = WIKIPEDIA_SUMMARY_URL.format(entity=encoded_entity)

    try:
        wikipedia_response = requests.get(
            summary_url, timeout=timeout_seconds, headers={"User-Agent": WIKIPEDIA_USER_AGENT}
        )
    except requests.Timeout:
        return {
            "entity": entity_name,
            "summary": "Wikipedia fetch timed out",
            "url": summary_url,
            "found": False,
        }
    except requests.RequestException as request_error:
        return {
            "entity": entity_name,
            "summary": f"Wikipedia fetch failed: {request_error}",
            "url": summary_url,
            "found": False,
        }

    if wikipedia_response.status_code == 404:
        return {
            "entity": entity_name,
            "summary": f"No Wikipedia article found for '{entity_name}'",
            "url": summary_url,
            "found": False,
        }

    if wikipedia_response.status_code != 200:
        return {
            "entity": entity_name,
            "summary": f"Wikipedia returned HTTP {wikipedia_response.status_code}",
            "url": summary_url,
            "found": False,
        }

    response_payload = wikipedia_response.json()
    return {
        "entity": entity_name,
        "summary": response_payload.get("extract", ""),
        "url": response_payload.get("content_urls", {}).get("desktop", {}).get("page", summary_url),
        "found": True,
    }


def synthesise_briefing(topic: str, entity_summaries: list[dict]) -> str:
    """Stage 3: synthesise a professional briefing from the gathered summaries."""
    system_prompt = "You are a professional analyst. Write a concise briefing document."

    formatted_summaries = "\n".join(
        f"## {entity_summary['entity']}\n{entity_summary['summary']}\n"
        for entity_summary in entity_summaries
    )
    user_prompt = (
        f"Topic: {topic}\n\n"
        f"{formatted_summaries}\n"
        "Write a 300-400 word briefing covering: (1) what this topic is about, "
        "(2) the key entities involved, (3) why it matters. Cite entities inline."
    )

    try:
        return get_completion(user_prompt, system=system_prompt)
    except Exception as synthesis_error:
        raise StageError("synthesis", str(synthesis_error))

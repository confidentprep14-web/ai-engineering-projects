import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import requests

import pipeline as pipeline_module
import stages as stages_module
from pipeline import run_pipeline
from stages import StageError, extract_entities, fetch_entity_summaries


def test_extract_entities_returns_list_of_strings(monkeypatch):
    monkeypatch.setattr(
        stages_module,
        "get_completion",
        lambda prompt, system="": '["Python", "Guido van Rossum", "CPython"]',
    )

    extracted_entities = extract_entities("Python language")

    assert extracted_entities == ["Python", "Guido van Rossum", "CPython"]


def test_extract_entities_raises_stage_error_on_bad_json(monkeypatch):
    monkeypatch.setattr(stages_module, "get_completion", lambda prompt, system="": "not json")

    try:
        extract_entities("anything")
        assert False, "expected StageError to be raised"
    except StageError as stage_error:
        assert stage_error.stage_name == "entity extraction"


def test_fetch_entity_summaries_handles_404(monkeypatch):
    class FakeResponse:
        def __init__(self, status_code, payload=None):
            self.status_code = status_code
            self._payload = payload or {}

        def json(self):
            return self._payload

    def fake_get(url, timeout, headers=None):
        if "Missing_Entity" in url:
            return FakeResponse(404)
        return FakeResponse(
            200,
            {
                "extract": "A real summary.",
                "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Found_Entity"}},
            },
        )

    monkeypatch.setattr(requests, "get", fake_get)

    entity_summaries = fetch_entity_summaries(["Missing Entity", "Found Entity"])

    summaries_by_entity = {entity_summary["entity"]: entity_summary for entity_summary in entity_summaries}
    assert summaries_by_entity["Missing Entity"]["found"] is False
    assert summaries_by_entity["Found Entity"]["found"] is True
    assert summaries_by_entity["Found Entity"]["summary"] == "A real summary."


def test_fetch_entity_summaries_handles_timeout(monkeypatch):
    def fake_get_that_times_out(url, timeout, headers=None):
        raise requests.Timeout("simulated timeout")

    monkeypatch.setattr(requests, "get", fake_get_that_times_out)

    entity_summaries = fetch_entity_summaries(["Slow Entity"])

    assert entity_summaries[0]["found"] is False
    assert "timed out" in entity_summaries[0]["summary"]


def test_pipeline_records_stage_latencies(monkeypatch):
    monkeypatch.setattr(pipeline_module, "extract_entities", lambda topic: ["Entity A", "Entity B"])
    monkeypatch.setattr(
        pipeline_module,
        "fetch_entity_summaries",
        lambda entities: [
            {"entity": entity_name, "summary": "a summary", "url": "https://example.org", "found": True}
            for entity_name in entities
        ],
    )
    monkeypatch.setattr(
        pipeline_module, "synthesise_briefing", lambda topic, entity_summaries: "a synthesised briefing"
    )

    pipeline_result = run_pipeline("test topic")

    assert set(pipeline_result.stage_latencies_ms.keys()) == {"extract", "fetch", "synthesise"}
    assert all(latency_ms >= 0 for latency_ms in pipeline_result.stage_latencies_ms.values())
    assert all(isinstance(latency_ms, int) for latency_ms in pipeline_result.stage_latencies_ms.values())

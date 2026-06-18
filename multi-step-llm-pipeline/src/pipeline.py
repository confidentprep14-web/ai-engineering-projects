import time
from dataclasses import dataclass, field

from stages import extract_entities, fetch_entity_summaries, synthesise_briefing


@dataclass
class PipelineResult:
    topic: str
    entities: list[str]
    entity_summaries: list[dict]
    briefing: str
    stage_latencies_ms: dict[str, int] = field(default_factory=dict)
    total_latency_ms: int = 0
    errors: list[str] = field(default_factory=list)


def _time_stage(stage_label: str, stage_fn, *args) -> tuple:
    """Run one stage, returning (result, elapsed_ms). Re-raises StageError as-is."""
    started_at = time.perf_counter()
    stage_result = stage_fn(*args)
    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    return stage_result, elapsed_ms


def run_pipeline(topic: str) -> PipelineResult:
    """Run entity extraction, Wikipedia enrichment, and briefing synthesis in sequence.

    Each stage is timed independently. If a stage raises StageError, the
    error is printed and re-raised immediately — later stages never run on
    a broken upstream result. Wikipedia misses are non-fatal and collected
    into `errors` instead of aborting the run.
    """
    stage_latencies_ms = {}
    pipeline_started_at = time.perf_counter()

    print("[Stage 1/3] Extracting entities...", end=" ", flush=True)
    try:
        entities, extract_latency_ms = _time_stage("extract", extract_entities, topic)
    except Exception as extraction_error:
        print(f"✗ {extraction_error}")
        raise
    stage_latencies_ms["extract"] = extract_latency_ms
    print(f"✓ {len(entities)} entities ({extract_latency_ms:,}ms)")

    print("[Stage 2/3] Fetching Wikipedia data...", end=" ", flush=True)
    try:
        entity_summaries, fetch_latency_ms = _time_stage("fetch", fetch_entity_summaries, entities)
    except Exception as fetch_error:
        print(f"✗ {fetch_error}")
        raise
    stage_latencies_ms["fetch"] = fetch_latency_ms
    found_count = sum(1 for entity_summary in entity_summaries if entity_summary["found"])
    print(f"✓ {found_count}/{len(entity_summaries)} found ({fetch_latency_ms:,}ms)")

    not_found_errors = [
        f"No Wikipedia article found for '{entity_summary['entity']}'"
        for entity_summary in entity_summaries
        if not entity_summary["found"]
    ]

    print("[Stage 3/3] Synthesising briefing...", end=" ", flush=True)
    try:
        briefing, synthesise_latency_ms = _time_stage(
            "synthesise", synthesise_briefing, topic, entity_summaries
        )
    except Exception as synthesis_error:
        print(f"✗ {synthesis_error}")
        raise
    stage_latencies_ms["synthesise"] = synthesise_latency_ms
    print(f"✓ done ({synthesise_latency_ms:,}ms)")

    total_latency_ms = int((time.perf_counter() - pipeline_started_at) * 1000)
    print(f"\nTotal: {total_latency_ms:,}ms")

    return PipelineResult(
        topic=topic,
        entities=entities,
        entity_summaries=entity_summaries,
        briefing=briefing,
        stage_latencies_ms=stage_latencies_ms,
        total_latency_ms=total_latency_ms,
        errors=not_found_errors,
    )

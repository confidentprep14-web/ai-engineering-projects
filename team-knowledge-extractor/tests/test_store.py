"""Tests for src/store.py — local JSON knowledge store.

Pure file/dict logic: no LLM call involved. Each test uses a temp store
path (pytest tmp_path) so tests never touch the real .knowledge_store.json.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from extractor import Decision  # noqa: E402
from store import KnowledgeStore  # noqa: E402


def _decision(source_file: str, **overrides) -> Decision:
    defaults = dict(
        id="abc123def456",
        date="2024-01-15",
        decision="A decision",
        rationale="A rationale",
        author="someone",
        tags=["misc"],
        source_file=source_file,
        source_type="github_issue",
        raw_title="A title",
    )
    defaults.update(overrides)
    return Decision(**defaults)


def test_empty_search_query_returns_all_results(tmp_path):
    """Spec test 4: search_keyword_recency('') with no keyword filter must
    return all 3 saved decisions."""
    store = KnowledgeStore(store_path=str(tmp_path / "store.json"))
    store.save(_decision("a.json"))
    store.save(_decision("b.json"))
    store.save(_decision("c.json"))

    results = store.search_keyword_recency("", top_k=10)

    assert len(results) == 3


def test_duplicate_source_file_updates_in_place(tmp_path):
    """Spec test 5: saving two decisions with the same source_file must
    leave exactly 1 decision in the store, not 2."""
    store = KnowledgeStore(store_path=str(tmp_path / "store.json"))
    store.save(_decision("issue_42.json", decision="First version"))
    store.save(_decision("issue_42.json", decision="Updated version"))

    all_decisions = store.list_all()

    assert len(all_decisions) == 1
    assert all_decisions[0].decision == "Updated version"


def test_store_persists_across_instances(tmp_path):
    store_path = str(tmp_path / "store.json")
    store = KnowledgeStore(store_path=store_path)
    store.save(_decision("a.json"))

    reloaded = KnowledgeStore(store_path=store_path)
    assert len(reloaded.list_all()) == 1


def test_store_initializes_empty_when_file_missing(tmp_path):
    store = KnowledgeStore(store_path=str(tmp_path / "does_not_exist.json"))
    assert store.list_all() == []


def test_list_all_sorted_by_date_descending(tmp_path):
    store = KnowledgeStore(store_path=str(tmp_path / "store.json"))
    store.save(_decision("old.json", date="2020-01-01"))
    store.save(_decision("new.json", date="2024-01-01"))

    all_decisions = store.list_all()

    assert all_decisions[0].source_file == "new.json"
    assert all_decisions[1].source_file == "old.json"


def test_export_json_writes_full_store(tmp_path):
    store = KnowledgeStore(store_path=str(tmp_path / "store.json"))
    store.save(_decision("a.json"))

    export_path = tmp_path / "export.json"
    store.export_json(str(export_path))

    assert export_path.exists()
    import json

    exported = json.loads(export_path.read_text())
    assert len(exported["decisions"]) == 1


def test_corrupted_store_starts_fresh(tmp_path, capsys):
    store_path = tmp_path / "store.json"
    store_path.write_text("{not valid json")

    store = KnowledgeStore(store_path=str(store_path))

    assert store.list_all() == []

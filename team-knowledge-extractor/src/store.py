"""Local JSON knowledge store: load, save (with dedup by source_file),
search, and export. One JSON file, loaded on startup, written after
every save — fast enough for hundreds of decisions, and the duplicate
detection by source_file makes re-running --extract idempotent.
"""

import json
import os
from dataclasses import asdict
from datetime import datetime, timezone

from extractor import Decision
from searcher import rank_decisions


class KnowledgeStore:
    def __init__(self, store_path: str = None):
        self.store_path = store_path or os.environ.get("STORE_PATH", ".knowledge_store.json")
        self._data = self._load()

    def _load(self) -> dict:
        if not os.path.exists(self.store_path):
            return {"decisions": [], "last_updated": None}

        try:
            with open(self.store_path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            print("Corrupted store — starting fresh")
            return {"decisions": [], "last_updated": None}

        if not isinstance(data, dict) or "decisions" not in data:
            print("Corrupted store — starting fresh")
            return {"decisions": [], "last_updated": None}

        return data

    def _write(self) -> None:
        self._data["last_updated"] = datetime.now(timezone.utc).isoformat()
        with open(self.store_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def save(self, decision: Decision) -> None:
        """Add a decision, updating in place if source_file already exists."""
        decision_dict = asdict(decision)
        decisions = self._data["decisions"]

        for idx, existing in enumerate(decisions):
            if existing.get("source_file") == decision.source_file:
                decisions[idx] = decision_dict
                break
        else:
            decisions.append(decision_dict)

        self._write()
        print(f'Saved: "{decision.raw_title}"')

    def search_keyword_recency(self, query: str, top_k: int = 5) -> list[Decision]:
        decisions = self.list_all()
        recency_weight = float(os.environ.get("RECENCY_WEIGHT", "0.3"))
        return rank_decisions(query, decisions, recency_weight=recency_weight, top_k=top_k)

    def list_all(self) -> list[Decision]:
        """All decisions as Decision objects, sorted by date descending."""
        decisions = [Decision(**d) for d in self._data["decisions"]]
        return sorted(decisions, key=lambda d: d.date or "", reverse=True)

    def export_json(self, output_path: str) -> None:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

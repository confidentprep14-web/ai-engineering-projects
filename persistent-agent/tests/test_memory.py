import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import agent as agent_module
from memory import MemoryStore


def _new_memory_store() -> MemoryStore:
    """Create a MemoryStore backed by a fresh temporary SQLite file."""
    db_path = tempfile.mktemp(suffix=".db")
    return MemoryStore(db_path)


def test_save_and_load_messages_round_trips():
    memory_store = _new_memory_store()

    memory_store.save_message("default", "user", "hello")
    memory_store.save_message("default", "assistant", "hi there")
    memory_store.save_message("default", "user", "what's up")

    loaded_messages = memory_store.load_recent_messages("default", limit=10)

    assert len(loaded_messages) == 3
    assert loaded_messages[0] == {"role": "user", "content": "hello"}
    assert loaded_messages[1] == {"role": "assistant", "content": "hi there"}
    assert loaded_messages[2] == {"role": "user", "content": "what's up"}


def test_load_recent_messages_respects_limit():
    memory_store = _new_memory_store()

    for message_index in range(10):
        memory_store.save_message("default", "user", f"message {message_index}")

    loaded_messages = memory_store.load_recent_messages("default", limit=3)

    assert len(loaded_messages) == 3
    assert loaded_messages[-1]["content"] == "message 9"
    assert loaded_messages[0]["content"] == "message 7"


def test_save_fact_and_load_top_facts():
    memory_store = _new_memory_store()

    memory_store.save_fact("user_name", "Alice", 0.95)
    memory_store.save_fact("user_role", "engineer", 0.7)

    top_facts = memory_store.load_top_facts(limit=2)

    fact_keys = [fact["key"] for fact in top_facts]
    assert "user_name" in fact_keys
    assert len(top_facts) == 2


def test_unique_constraint_replaces_existing_fact():
    memory_store = _new_memory_store()

    memory_store.save_fact("user_name", "Alice", 0.9)
    memory_store.save_fact("user_name", "Bob", 0.95)

    all_facts = memory_store.load_all_facts()
    user_name_facts = [fact for fact in all_facts if fact["key"] == "user_name"]

    assert len(user_name_facts) == 1
    assert user_name_facts[0]["value"] == "Bob"


def test_clear_all_removes_all_records():
    memory_store = _new_memory_store()

    memory_store.save_message("default", "user", "one")
    memory_store.save_message("default", "user", "two")
    memory_store.save_message("default", "user", "three")
    memory_store.save_fact("user_name", "Alice", 0.9)
    memory_store.save_fact("user_role", "engineer", 0.7)

    memory_store.clear_all()

    assert memory_store.get_message_count() == 0
    assert memory_store.get_fact_count() == 0


def test_extract_facts_returns_empty_list_on_non_factual_message(monkeypatch):
    monkeypatch.setattr(agent_module, "get_completion", lambda messages, system="": "[]")

    extracted_facts = agent_module.extract_facts("What time is it?", "user")

    assert extracted_facts == []


def test_messages_survive_a_simulated_process_restart():
    """Closing and reopening a MemoryStore against the same file must see prior writes."""
    db_path = tempfile.mktemp(suffix=".db")

    first_process_memory = MemoryStore(db_path)
    first_process_memory.save_message("default", "user", "My name is Alex")
    first_process_memory.save_fact("user_name", "Alex", 0.95)
    first_process_memory.close()

    second_process_memory = MemoryStore(db_path)
    reloaded_messages = second_process_memory.load_recent_messages("default", limit=10)
    reloaded_facts = second_process_memory.load_all_facts()

    assert reloaded_messages == [{"role": "user", "content": "My name is Alex"}]
    assert reloaded_facts[0]["key"] == "user_name"
    assert reloaded_facts[0]["value"] == "Alex"

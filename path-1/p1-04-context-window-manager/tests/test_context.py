import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest

import context as context_module
from context import ContextManager
from tokenizer import count_tokens

TEST_MODEL = "claude-3-5-haiku-20241022"


def test_token_count_increases_with_messages():
    context_manager = ContextManager(context_limit=8192, warn_threshold=0.8, strategy="sliding", keep_recent=6)

    previous_token_count = context_manager.get_token_count(TEST_MODEL)
    assert previous_token_count == 0

    for message_index in range(5):
        context_manager.add_message("user", f"This is test message number {message_index}")
        current_token_count = context_manager.get_token_count(TEST_MODEL)
        assert current_token_count > previous_token_count
        previous_token_count = current_token_count


def test_is_approaching_limit_triggers_correctly():
    context_manager = ContextManager(context_limit=100, warn_threshold=0.8, strategy="sliding", keep_recent=6)

    assert context_manager.is_approaching_limit(TEST_MODEL) is False

    while context_manager.get_token_count(TEST_MODEL) <= 80:
        context_manager.add_message("user", "padding words to push the token count upward steadily")

    assert context_manager.is_approaching_limit(TEST_MODEL) is True


def test_sliding_window_removes_oldest_messages_first():
    context_manager = ContextManager(context_limit=120, warn_threshold=0.8, strategy="sliding", keep_recent=6)
    for message_index in range(10):
        context_manager.add_message("user", f"message body number {message_index} with some extra padding text")

    messages_before_compression = list(context_manager.messages)
    removed_count = context_manager.apply_sliding_window(TEST_MODEL)

    assert removed_count > 0
    assert context_manager.messages == messages_before_compression[removed_count:]
    assert context_manager.get_token_count(TEST_MODEL) <= 120 * context_module.SLIDING_WINDOW_TARGET_FRACTION


def test_sliding_window_preserves_most_recent_messages():
    context_manager = ContextManager(context_limit=150, warn_threshold=0.8, strategy="sliding", keep_recent=6)
    for old_index in range(1, 9):
        context_manager.add_message("user", f"old-{old_index} filler text to take up token space here")
    context_manager.add_message("user", "recent-1 filler text to take up token space here")
    context_manager.add_message("user", "recent-2 filler text to take up token space here")

    context_manager.apply_sliding_window(TEST_MODEL)

    remaining_contents = [message["content"] for message in context_manager.messages]
    assert any("recent-2" in content for content in remaining_contents)


def test_export_and_load_round_trips_messages(tmp_path):
    context_manager = ContextManager(context_limit=8192, warn_threshold=0.8, strategy="summarise", keep_recent=6)
    context_manager.add_message("user", "hello there")
    context_manager.add_message("assistant", "hi, how can I help?")
    context_manager.add_message("user", "tell me about context windows")

    export_path = tmp_path / "session.json"
    context_manager.export(str(export_path))

    loaded_manager = ContextManager.load(str(export_path))

    assert loaded_manager.messages == context_manager.messages
    assert loaded_manager.strategy == "summarise"


def test_count_tokens_is_deterministic():
    messages = [
        {"role": "user", "content": "What is the capital of France?"},
        {"role": "assistant", "content": "The capital of France is Paris."},
    ]

    first_count = count_tokens(messages, TEST_MODEL)
    second_count = count_tokens(messages, TEST_MODEL)

    assert first_count == second_count
    assert first_count > 0


def test_load_raises_file_not_found_for_missing_session():
    with pytest.raises(FileNotFoundError):
        ContextManager.load("/nonexistent/path/for/context-manager/session.json")


def test_summarise_compression_falls_back_to_sliding_on_llm_failure(monkeypatch):
    def _raise_completion_error(messages, system=""):
        raise RuntimeError("simulated LLM timeout")

    monkeypatch.setattr(context_module, "get_completion", _raise_completion_error)

    context_manager = ContextManager(context_limit=150, warn_threshold=0.8, strategy="summarise", keep_recent=2)
    for message_index in range(8):
        context_manager.add_message("user", f"message body number {message_index} with extra padding text here")

    messages_before_compression = list(context_manager.messages)
    summary_text = context_manager.apply_summarise_compression(TEST_MODEL)

    assert summary_text == ""
    assert len(context_manager.messages) < len(messages_before_compression)


def test_compress_if_needed_raises_for_unknown_strategy():
    context_manager = ContextManager(context_limit=50, warn_threshold=0.8, strategy="bogus", keep_recent=2)
    for message_index in range(10):
        context_manager.add_message("user", f"padding message {message_index} to exceed the small token limit")

    with pytest.raises(ValueError):
        context_manager.compress_if_needed(TEST_MODEL)

"""Context window management strategies for multi-turn conversations.

Two compression strategies are implemented: sliding window (drop oldest
messages, zero cost) and summarisation (compress old turns into one summary
message via an extra LLM call). ContextManager tracks token usage against a
configured limit and applies whichever strategy is active once the limit is
approached.
"""

import json
import sys

from llm import get_completion
from tokenizer import count_tokens

DEFAULT_CONTEXT_LIMIT = 8192
SLIDING_WINDOW_TARGET_FRACTION = 0.7
COMPRESSION_TRIGGER_FRACTION = 0.85
SUMMARY_PROMPT_TEMPLATE = (
    "Summarise this conversation history into 2-3 sentences, preserving key "
    "facts and decisions:\n{conversation_text}"
)


class ContextManager:
    def __init__(self, context_limit: int, warn_threshold: float, strategy: str, keep_recent: int):
        if context_limit is None:
            print(f"CONTEXT_LIMIT not set — defaulting to {DEFAULT_CONTEXT_LIMIT} tokens")
            context_limit = DEFAULT_CONTEXT_LIMIT

        self.context_limit = context_limit
        self.warn_threshold = warn_threshold
        self.strategy = strategy
        self.keep_recent = keep_recent
        self.messages: list[dict] = []
        self.sliding_window_fired_count = 0
        self.summarise_fired_count = 0

    def add_message(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})

    def get_token_count(self, model: str) -> int:
        return count_tokens(self.messages, model)

    def is_approaching_limit(self, model: str) -> bool:
        return self.get_token_count(model) / self.context_limit >= self.warn_threshold

    def apply_sliding_window(self, model: str) -> int:
        """Drop the oldest messages until usage falls under the sliding-window target."""
        removed_message_count = 0
        target_tokens = self.context_limit * SLIDING_WINDOW_TARGET_FRACTION

        while self.messages and self.get_token_count(model) > target_tokens:
            dropped_message = self.messages.pop(0)
            preview = dropped_message["content"][:50]
            print(f'Dropped [{dropped_message["role"]}]: "{preview}..."', file=sys.stderr)
            removed_message_count += 1

        self.sliding_window_fired_count += 1
        return removed_message_count

    def apply_summarise_compression(self, model: str) -> str:
        """Compress all but the most recent `keep_recent` messages into one summary turn."""
        messages_to_summarise = self.messages[: -self.keep_recent] if self.keep_recent else self.messages[:]

        if not messages_to_summarise:
            self.summarise_fired_count += 1
            return ""

        conversation_text = "\n".join(
            f'{message["role"]}: {message["content"]}' for message in messages_to_summarise
        )
        summary_prompt = SUMMARY_PROMPT_TEMPLATE.format(conversation_text=conversation_text)

        try:
            summary_text = get_completion([{"role": "user", "content": summary_prompt}])
        except Exception as summarisation_error:
            print(
                f"Warning: summarisation LLM call failed ({summarisation_error}) — "
                "falling back to sliding window for this cycle",
                file=sys.stderr,
            )
            self.apply_sliding_window(model)
            return ""

        recent_messages = self.messages[-self.keep_recent:] if self.keep_recent else []
        summary_message = {"role": "assistant", "content": f"[Summary]: {summary_text}"}
        self.messages = [summary_message] + recent_messages
        self.summarise_fired_count += 1
        return summary_text

    def compress_if_needed(self, model: str) -> bool:
        if self.get_token_count(model) <= self.context_limit * COMPRESSION_TRIGGER_FRACTION:
            return False

        if self.strategy == "sliding":
            self.apply_sliding_window(model)
        elif self.strategy == "summarise":
            self.apply_summarise_compression(model)
        else:
            raise ValueError(f"Unknown CONTEXT_STRATEGY={self.strategy}. Use sliding or summarise")

        return True

    def export(self, path: str) -> None:
        with open(path, "w") as session_file:
            json.dump({"messages": self.messages, "strategy": self.strategy}, session_file, indent=2)

    @classmethod
    def load(cls, path: str) -> "ContextManager":
        try:
            with open(path, "r") as session_file:
                session_data = json.load(session_file)
        except FileNotFoundError:
            raise FileNotFoundError(f"Session file not found: {path}")

        loaded_manager = cls(
            context_limit=DEFAULT_CONTEXT_LIMIT,
            warn_threshold=0.8,
            strategy=session_data.get("strategy", "sliding"),
            keep_recent=6,
        )
        loaded_manager.messages = session_data["messages"]
        return loaded_manager

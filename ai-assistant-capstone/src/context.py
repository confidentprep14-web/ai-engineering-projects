"""Context window management for multi-turn conversations.

Same ContextManager class and sliding-window strategy as the standalone
context-window-manager project (p1-04), adapted to call this project's
src/llm.get_completion(messages, system, tools) signature instead of the
single-string version. Two compression strategies: sliding window (drop
oldest messages, zero cost) and summarise (compress old turns into one
summary message via an extra LLM call). CONTEXT_STRATEGY in .env picks
which one /chat uses.
"""
import sys

from src.tokenizer import count_tokens

DEFAULT_CONTEXT_LIMIT = 8192
SLIDING_WINDOW_TARGET_FRACTION = 0.7
COMPRESSION_TRIGGER_FRACTION = 0.85
SUMMARY_PROMPT_TEMPLATE = (
    "Summarise this conversation history into 2-3 sentences, preserving key "
    "facts and decisions:\n{conversation_text}"
)


class ContextManager:
    def __init__(self, context_limit: int, strategy: str = "sliding", keep_recent: int = 6):
        if context_limit is None:
            print(f"MAX_CONTEXT_TOKENS not set — defaulting to {DEFAULT_CONTEXT_LIMIT} tokens")
            context_limit = DEFAULT_CONTEXT_LIMIT

        self.context_limit = context_limit
        self.strategy = strategy
        self.keep_recent = keep_recent
        self.messages: list[dict] = []
        self.sliding_window_fired_count = 0
        self.summarise_fired_count = 0

    def add_message(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})

    def load_messages(self, messages: list[dict]) -> None:
        """Replace the working set with messages loaded from the database."""
        self.messages = list(messages)

    def get_token_count(self, model: str) -> int:
        return count_tokens(self.messages, model)

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
        from src.llm import get_completion

        messages_to_summarise = self.messages[: -self.keep_recent] if self.keep_recent else self.messages[:]

        if not messages_to_summarise:
            self.summarise_fired_count += 1
            return ""

        conversation_text = "\n".join(
            f'{message["role"]}: {message["content"]}' for message in messages_to_summarise
        )
        summary_prompt = SUMMARY_PROMPT_TEMPLATE.format(conversation_text=conversation_text)

        try:
            summary_result = get_completion([{"role": "user", "content": summary_prompt}])
            summary_text = summary_result["content"]
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

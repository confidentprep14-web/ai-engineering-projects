"""Approximate token counting for chat messages.

tiktoken counts tokens exactly for OpenAI models. For Claude and Ollama models
there is no public exact tokenizer, so this module falls back to tiktoken's
cl100k_base encoding as a compatible approximation. This is why CONTEXT_LIMIT
should be set conservatively (see GUIDE.md).
"""

import tiktoken

MESSAGE_OVERHEAD_TOKENS = 4


def _get_encoding(model: str):
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        return tiktoken.get_encoding("cl100k_base")


def count_string_tokens(text: str, model: str) -> int:
    """Count tokens in a single string using the model's encoding (or a fallback)."""
    token_encoding = _get_encoding(model)
    return len(token_encoding.encode(text))


def count_tokens(messages: list[dict], model: str) -> int:
    """Approximate the total token count of a list of chat messages.

    Adds a fixed per-message overhead to account for role/formatting tokens
    that the raw text encoding does not capture.
    """
    token_encoding = _get_encoding(model)
    total_token_count = 0
    for message in messages:
        total_token_count += len(token_encoding.encode(message["content"]))
        total_token_count += MESSAGE_OVERHEAD_TOKENS
    return total_token_count

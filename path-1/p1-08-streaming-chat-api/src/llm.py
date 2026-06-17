"""Streaming completion wrapper, one branch per LLM provider.

stream_completion() yields (token_text, prompt_tokens, completion_tokens)
tuples. Token counts are 0 on every yield except the last, where the real
usage numbers (from the provider, or counted via tiktoken as a fallback)
are attached so the caller can log cost once the stream finishes.
"""
from typing import Iterator

import tiktoken

from src.config import config

_TOKENIZER = tiktoken.get_encoding("cl100k_base")


def _count_tokens(text: str) -> int:
    return len(_TOKENIZER.encode(text))


def stream_completion(prompt: str, system: str = "") -> Iterator[tuple[str, int, int]]:
    if config.llm_provider == "anthropic":
        yield from _stream_anthropic(prompt, system)
    elif config.llm_provider == "openai":
        yield from _stream_openai(prompt, system)
    elif config.llm_provider == "ollama":
        yield from _stream_ollama(prompt, system)
    else:
        raise ValueError(f"Unknown LLM_PROVIDER={config.llm_provider!r}")


def _stream_anthropic(prompt: str, system: str) -> Iterator[tuple[str, int, int]]:
    import anthropic

    client = anthropic.Anthropic(api_key=config.llm_api_key)
    with client.messages.stream(
        model=config.llm_model,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text_delta in stream.text_stream:
            yield text_delta, 0, 0
        final_message = stream.get_final_message()
        yield (
            "",
            final_message.usage.input_tokens,
            final_message.usage.output_tokens,
        )


def _stream_openai(prompt: str, system: str) -> Iterator[tuple[str, int, int]]:
    import openai

    client = openai.OpenAI(api_key=config.llm_api_key)
    messages = [{"role": "user", "content": prompt}]
    if system:
        messages = [{"role": "system", "content": system}] + messages

    completion_chunks = client.chat.completions.create(
        model=config.llm_model,
        messages=messages,
        stream=True,
        stream_options={"include_usage": True},
    )
    prompt_tokens = 0
    completion_tokens = 0
    for chunk in completion_chunks:
        if chunk.usage is not None:
            prompt_tokens = chunk.usage.prompt_tokens
            completion_tokens = chunk.usage.completion_tokens
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content, 0, 0
    yield "", prompt_tokens, completion_tokens


def _stream_ollama(prompt: str, system: str) -> Iterator[tuple[str, int, int]]:
    import ollama

    messages = [{"role": "user", "content": prompt}]
    if system:
        messages = [{"role": "system", "content": system}] + messages

    completion_text = ""
    for chunk in ollama.chat(model=config.llm_model, messages=messages, stream=True):
        content = chunk["message"]["content"]
        completion_text += content
        yield content, 0, 0

    prompt_tokens = _count_tokens(prompt + system)
    completion_tokens = _count_tokens(completion_text)
    yield "", prompt_tokens, completion_tokens

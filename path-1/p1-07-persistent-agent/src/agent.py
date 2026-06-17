"""Agent loop: loads memory, chats, extracts facts, tracks memory hit rate."""

import json
import os

from llm import get_completion
from memory import MemoryStore

FACT_EXTRACTION_SYSTEM_PROMPT = (
    "Extract memorable facts from this user message. Return JSON array of objects: "
    '[{"key": "fact_category", "value": "fact_value", "confidence": 0.0-1.0}]. '
    "Examples: user_name, user_role, preferred_language, project_name. "
    "Return empty array [] if no memorable facts present. Return ONLY JSON."
)

BASE_SYSTEM_PROMPT = "You are a helpful assistant with memory of past conversations."

MIN_FACT_CONFIDENCE_TO_INJECT = 0.8


def extract_facts(message_content: str, role: str) -> list[dict]:
    """Ask the LLM to pull structured facts out of a user message.

    Never raises — a malformed extraction is noise, not a reason to crash the
    conversation. Only user messages are considered worth mining for facts.
    """
    if role != "user":
        return []

    try:
        raw_extraction = get_completion(
            messages=[{"role": "user", "content": message_content}],
            system=FACT_EXTRACTION_SYSTEM_PROMPT,
        )
        parsed_facts = json.loads(raw_extraction)
    except (json.JSONDecodeError, ValueError, KeyError, IndexError):
        return []

    if not isinstance(parsed_facts, list):
        return []

    extracted_facts = []
    for fact in parsed_facts:
        if not isinstance(fact, dict):
            continue
        if "key" not in fact or "value" not in fact:
            continue
        extracted_facts.append(
            {
                "key": str(fact["key"]),
                "value": str(fact["value"]),
                "confidence": float(fact.get("confidence", 0.0)),
            }
        )
    return extracted_facts


def build_system_prompt(facts: list[dict]) -> str:
    """Compose the system prompt, injecting only facts worth trusting."""
    high_confidence_facts = [fact for fact in facts if fact["confidence"] >= MIN_FACT_CONFIDENCE_TO_INJECT]
    if not high_confidence_facts:
        return BASE_SYSTEM_PROMPT

    fact_lines = "\n".join(
        f"- {fact['key']}: {fact['value']} (confidence: {fact['confidence']:.0%})"
        for fact in high_confidence_facts
    )
    return f"{BASE_SYSTEM_PROMPT}\nKnown facts about the user:\n{fact_lines}"


def run_session(memory: MemoryStore, session_id: str) -> dict:
    """Run the interactive chat loop until the user quits or interrupts.

    Returns {"turns", "facts_extracted", "memory_hits"} so main.py can print
    the session summary and the memory hit rate.
    """
    recent_messages_limit = int(os.environ.get("RECENT_MESSAGES_LIMIT", "20"))
    top_facts_limit = int(os.environ.get("TOP_FACTS_LIMIT", "10"))

    loaded_history = memory.load_recent_messages(session_id, recent_messages_limit)
    known_facts = memory.load_top_facts(top_facts_limit)
    system_prompt = build_system_prompt(known_facts)

    print(f"\U0001f4da Loaded {len(loaded_history)} prior messages | {len(known_facts)} known facts")
    if known_facts:
        for fact in known_facts:
            print(f"  - {fact['key']}: {fact['value']} (confidence: {fact['confidence']:.0%})")
    print()

    turns = 0
    facts_extracted = 0
    memory_hits = 0
    conversation_history = list(loaded_history)

    while True:
        try:
            user_input = input("You: ")
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if user_input.strip().lower() == "quit":
            break
        if not user_input.strip():
            continue

        msg_id = memory.save_message(session_id, "user", user_input)

        new_facts = extract_facts(user_input, "user")
        for fact in new_facts:
            memory.save_fact(fact["key"], fact["value"], fact["confidence"], source_id=msg_id)
            facts_extracted += 1

        conversation_history.append({"role": "user", "content": user_input})
        assistant_response = get_completion(messages=conversation_history, system=system_prompt)
        print(f"Assistant: {assistant_response}")

        memory.save_message(session_id, "assistant", assistant_response)
        conversation_history.append({"role": "assistant", "content": assistant_response})

        if any(fact["value"].lower() in assistant_response.lower() for fact in known_facts + new_facts):
            memory_hits += 1

        turns += 1

    return {"turns": turns, "facts_extracted": facts_extracted, "memory_hits": memory_hits}

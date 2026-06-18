import argparse
import os
import sqlite3
import sys

from dotenv import load_dotenv

from agent import run_session
from memory import MemoryStore

DEFAULT_SESSION_ID = "default"


def show_memory(memory: MemoryStore) -> None:
    """Print every stored fact as a table plus the total message count."""
    facts = memory.load_all_facts()
    print(f"Messages stored: {memory.get_message_count()}")
    print(f"Facts stored: {len(facts)}")
    if not facts:
        return

    print(f"\n{'KEY':<25}{'VALUE':<30}{'CONFIDENCE':>10}")
    print("-" * 65)
    for fact in facts:
        print(f"{fact['key']:<25}{fact['value']:<30}{fact['confidence']:>9.0%}")


def clear_memory(memory: MemoryStore) -> None:
    """Wipe all history and facts after an explicit, exact 'yes' confirmation."""
    confirmation = input("Clear all memory? (yes/no): ")
    if confirmation.strip().lower() != "yes":
        print("Cancelled")
        return
    memory.clear_all()
    print("Memory cleared")


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Chat with an agent that remembers you across sessions.")
    parser.add_argument("--show-memory", action="store_true", help="Print stored facts and message count, then exit")
    parser.add_argument("--clear-memory", action="store_true", help="Wipe all stored history and facts")
    parser.add_argument("--session-id", default=DEFAULT_SESSION_ID, help="Memory session to use (default: 'default')")
    args = parser.parse_args()

    db_path = os.environ.get("MEMORY_DB_PATH", "./agent_memory.db")

    try:
        memory = MemoryStore(db_path)
    except sqlite3.OperationalError as db_error:
        print(f"Error: could not open memory database at {db_path}: {db_error}")
        sys.exit(1)

    try:
        if args.show_memory:
            show_memory(memory)
            return
        if args.clear_memory:
            clear_memory(memory)
            return

        try:
            session_result = run_session(memory, args.session_id)
        except ValueError as configuration_error:
            print(f"Error: {configuration_error}")
            sys.exit(1)
        except Exception as llm_or_network_error:
            print(f"Error: {llm_or_network_error}")
            sys.exit(1)

        turns = session_result["turns"]
        memory_hits = session_result["memory_hits"]
        hit_rate = (memory_hits / turns) if turns else 0.0
        print(
            f"Session ended: {turns} turns | {session_result['facts_extracted']} new facts extracted "
            f"| Memory hits: {memory_hits}/{turns} ({hit_rate:.0%})"
        )
    finally:
        memory.close()


if __name__ == "__main__":
    main()

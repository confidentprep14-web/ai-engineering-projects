import argparse
import os
import sys

from dotenv import load_dotenv

from context import ContextManager
from llm import get_completion


def _build_context_manager(strategy_override: str | None) -> ContextManager:
    context_limit_env = os.environ.get("CONTEXT_LIMIT")
    context_limit = int(context_limit_env) if context_limit_env else None
    warn_threshold = float(os.environ.get("WARN_THRESHOLD", 0.8))
    strategy = strategy_override or os.environ.get("CONTEXT_STRATEGY", "sliding")
    keep_recent = int(os.environ.get("SUMMARISE_KEEP_RECENT", 6))
    return ContextManager(context_limit, warn_threshold, strategy, keep_recent)


def run_interactive_session(context_manager: ContextManager, model: str, save_path: str | None) -> None:
    print(f"Strategy: {context_manager.strategy} | Context limit: {context_manager.context_limit} tokens")
    print("Type a message, or 'quit' to exit.")

    try:
        while True:
            print("You:")
            user_input = input("> ")
            if user_input.strip().lower() == "quit":
                break

            context_manager.add_message("user", user_input)

            if context_manager.is_approaching_limit(model):
                token_fraction_used = context_manager.get_token_count(model) / context_manager.context_limit
                print(
                    f"⚠ Context at {token_fraction_used:.0%} of limit — "
                    f"{context_manager.strategy} compression will apply"
                )

            context_manager.compress_if_needed(model)

            assistant_response = get_completion(context_manager.messages)
            context_manager.add_message("assistant", assistant_response)

            print(f"Assistant: {assistant_response}")
            token_count = context_manager.get_token_count(model)
            token_fraction_used = token_count / context_manager.context_limit
            print(f"\U0001F4CA Tokens used: {token_count}/{context_manager.context_limit} ({token_fraction_used:.0%})")
    except (KeyboardInterrupt, EOFError):
        print()
    finally:
        if save_path:
            context_manager.export(save_path)
            print(f"Session saved to {save_path}")
        print(
            f"Session ended: sliding window fired {context_manager.sliding_window_fired_count} times "
            f"| summarised {context_manager.summarise_fired_count} times"
        )


def _replay_session(saved_messages: list[dict], strategy: str, model: str, keep_recent: int) -> list[dict]:
    """Replay saved messages through a strategy without calling the LLM for user turns.

    Returns a list of per-turn snapshots so --compare can show what each strategy
    keeps or drops at each step, without spending API calls on a real replay.
    """
    replay_manager = ContextManager(
        context_limit=int(os.environ.get("CONTEXT_LIMIT") or 8192),
        warn_threshold=float(os.environ.get("WARN_THRESHOLD", 0.8)),
        strategy=strategy,
        keep_recent=keep_recent,
    )

    turn_snapshots = []
    for saved_message in saved_messages:
        replay_manager.add_message(saved_message["role"], saved_message["content"])
        compression_applied = replay_manager.compress_if_needed(model)
        turn_snapshots.append(
            {
                "messages_remaining": len(replay_manager.messages),
                "compression_applied": compression_applied,
            }
        )
    return turn_snapshots


def run_compare_mode(session_path: str, model: str, keep_recent: int) -> None:
    loaded_manager = ContextManager.load(session_path)
    saved_messages = loaded_manager.messages

    sliding_snapshots = _replay_session(saved_messages, "sliding", model, keep_recent)
    summarise_snapshots = _replay_session(saved_messages, "summarise", model, keep_recent)

    print(f"{'Turn':<6}{'Sliding: messages left':<28}{'Summarise: messages left':<28}")
    for turn_index in range(len(saved_messages)):
        sliding_state = sliding_snapshots[turn_index]
        summarise_state = summarise_snapshots[turn_index]
        sliding_note = "compressed" if sliding_state["compression_applied"] else ""
        summarise_note = "compressed" if summarise_state["compression_applied"] else ""
        print(
            f"{turn_index + 1:<6}"
            f"{str(sliding_state['messages_remaining']) + ' ' + sliding_note:<28}"
            f"{str(summarise_state['messages_remaining']) + ' ' + summarise_note:<28}"
        )


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Multi-turn chatbot with context window management.")
    parser.add_argument("--strategy", choices=["sliding", "summarise"], default=None, help="Force a compression strategy")
    parser.add_argument("--save", dest="save_path", default=None, help="Path to export the session JSON on exit")
    parser.add_argument("--compare", dest="compare_path", default=None, help="Replay a saved session through both strategies")
    args = parser.parse_args()

    model = os.environ.get("LLM_MODEL", "claude-3-5-haiku-20241022")
    keep_recent = int(os.environ.get("SUMMARISE_KEEP_RECENT", 6))

    try:
        if args.compare_path:
            run_compare_mode(args.compare_path, model, keep_recent)
            return

        context_manager = _build_context_manager(args.strategy)
        run_interactive_session(context_manager, model, args.save_path)
    except (FileNotFoundError, ValueError) as known_failure:
        print(f"Error: {known_failure}")
        sys.exit(1)


if __name__ == "__main__":
    main()

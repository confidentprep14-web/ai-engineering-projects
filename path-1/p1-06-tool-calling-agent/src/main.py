import argparse
import sys

from dotenv import load_dotenv

from agent import run_agent


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Ask a tool-calling agent a question.")
    parser.add_argument("question", help="The question to ask the agent")
    parser.add_argument("--max-iter", dest="max_iterations", type=int, default=None, help="Max agentic loop iterations")
    args = parser.parse_args()

    print(f"Question: {args.question}\n")

    try:
        agent_result = run_agent(args.question, max_iterations=args.max_iterations)
    except ValueError as configuration_error:
        print(f"Error: {configuration_error}")
        sys.exit(1)
    except Exception as llm_or_network_error:
        print(f"Error: {llm_or_network_error}")
        sys.exit(1)

    print(f"\nAnswer: {agent_result.final_answer}")

    max_reached_note = " (max reached)" if agent_result.hit_max_iterations else ""
    print(f"\n\U0001f4ca Tools used: {agent_result.tools_used} | Iterations: {agent_result.iterations}{max_reached_note}")


if __name__ == "__main__":
    main()

import argparse
import sys

from dotenv import load_dotenv

from pipeline import run_pipeline
from stages import StageError


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="3-stage LLM pipeline: entities -> Wikipedia -> briefing.")
    parser.add_argument("topic", help="Topic to build a briefing about")
    parser.add_argument("--output", dest="output_path", default=None, help="Path to save the briefing as a .md file")
    args = parser.parse_args()

    print(f'\nRunning pipeline for: "{args.topic}"\n')

    try:
        pipeline_result = run_pipeline(args.topic)
    except (StageError, ValueError) as known_failure:
        print(f"\nError: {known_failure}")
        sys.exit(1)
    except Exception as unexpected_llm_or_network_error:
        print(f"\nError: {unexpected_llm_or_network_error}")
        sys.exit(1)

    print(f"\n# Briefing: {pipeline_result.topic}\n")
    print(pipeline_result.briefing)

    if args.output_path:
        try:
            with open(args.output_path, "w") as output_file:
                output_file.write(f"# Briefing: {pipeline_result.topic}\n\n{pipeline_result.briefing}\n")
        except OSError as write_error:
            print(f"\nError: could not write to {args.output_path}: {write_error}")
            sys.exit(1)
        print(f"\nSaved to {args.output_path}")

    if pipeline_result.errors:
        not_found_entities = [
            entity_summary["entity"]
            for entity_summary in pipeline_result.entity_summaries
            if not entity_summary["found"]
        ]
        print(f"\n⚠ Not found: {not_found_entities}")


if __name__ == "__main__":
    main()

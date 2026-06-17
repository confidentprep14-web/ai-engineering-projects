"""CLI entry point: `run` evaluates one prompt against a suite, `diff`
evaluates two prompt versions and compares them side by side.

Exit code is 1 if any test case fails (or on a handled error) so this can
gate a CI pipeline.
"""
import argparse
import os
import sys

# Allow `python src/main.py` to find the `src` package by ensuring the
# project root (this file's grandparent) is on sys.path. Not needed when
# pytest imports this module, since rootdir is already on sys.path there.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import reporter, runner  # noqa: E402

DEFAULT_PROMPT_TEMPLATE = (
    "Answer this question using the context provided.\n\n"
    "Context: {context}\n\n"
    "Question: {input}"
)


def _load_prompt_template(path: str) -> str:
    if path is None:
        return DEFAULT_PROMPT_TEMPLATE
    with open(path, "r") as f:
        return f.read()


def cmd_run(args) -> int:
    try:
        suite = runner.load_suite(args.suite)
        prompt_template = _load_prompt_template(args.prompt)
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}")
        return 1

    print(f"Running {suite.get('suite_name', args.suite)} "
          f"({len(suite['test_cases'])} test cases)...\n")

    suite_result = runner.run_suite(suite, prompt_template)
    reporter.print_results_table(suite_result["results"], suite["scoring_dimensions"])

    summary = suite_result["summary"]
    pct = round(summary["pass_rate"] * 100)
    print(f"\nSummary: {summary['passed']}/{summary['total']} passed ({pct}%)")

    if args.output:
        reporter.save_json_report(suite_result, args.output)

    return 1 if summary["failed"] > 0 else 0


def cmd_diff(args) -> int:
    try:
        suite = runner.load_suite(args.suite)
        prompt_a = _load_prompt_template(args.prompt_a)
        prompt_b = _load_prompt_template(args.prompt_b)
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}")
        return 1

    print(f"Comparing prompts on {suite.get('suite_name', args.suite)} "
          f"({len(suite['test_cases'])} test cases)...\n")

    result_a = runner.run_suite(suite, prompt_a)
    result_b = runner.run_suite(suite, prompt_b)

    reporter.print_diff_table(result_a, result_b)

    total = result_a["summary"]["total"]
    print(f"\nPrompt A: {result_a['summary']['passed']}/{total} passed | "
          f"Prompt B: {result_b['summary']['passed']}/{total} passed")

    if args.output:
        reporter.save_json_report(
            {"prompt_a": result_a, "prompt_b": result_b}, args.output
        )

    any_failed = result_a["summary"]["failed"] > 0 or result_b["summary"]["failed"] > 0
    return 1 if any_failed else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="prompt-eval")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run a test suite against one prompt")
    run_parser.add_argument("--suite", required=True)
    run_parser.add_argument("--prompt", default=None)
    run_parser.add_argument("--output", default=None)
    run_parser.set_defaults(func=cmd_run)

    diff_parser = subparsers.add_parser("diff", help="Compare two prompt versions")
    diff_parser.add_argument("--suite", required=True)
    diff_parser.add_argument("--prompt-a", required=True, dest="prompt_a")
    diff_parser.add_argument("--prompt-b", required=True, dest="prompt_b")
    diff_parser.add_argument("--output", default=None)
    diff_parser.set_defaults(func=cmd_diff)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

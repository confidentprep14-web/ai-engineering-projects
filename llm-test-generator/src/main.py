"""CLI entry point — extracts public function metadata from a Python
file, generates pytest tests per function via an LLM, validates each
by actually running pytest (retrying with error context on failure),
and writes a final test file containing only tests that pass.
"""

import argparse
import os
import sys

from dotenv import load_dotenv
from generator import generate_tests_for_function
from parser import extract_function_metadata
from reporter import print_coverage_summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate pytest tests for a Python file's public functions via LLM."
    )
    parser.add_argument("source_file", help="Path to the Python file to generate tests for.")
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="After generating tests, run pytest-cov and print a coverage summary.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=None,
        help="Override MAX_RETRIES from the environment.",
    )
    return parser


def _build_imports(source_file: str) -> str:
    source_dir = os.path.dirname(os.path.abspath(source_file)) or "."
    module_name = os.path.splitext(os.path.basename(source_file))[0]
    return f"import sys\nsys.path.insert(0, {source_dir!r})\nfrom {module_name} import *\n\n"


def run(source_file: str, coverage: bool, max_retries_override: int | None) -> int:
    load_dotenv()

    max_retries = max_retries_override or int(os.environ.get("MAX_RETRIES", "3"))
    output_dir = os.environ.get("OUTPUT_DIR", ".")

    functions = extract_function_metadata(source_file)
    print(f"Found {len(functions)} public functions")

    if not functions:
        print(f"No public functions found in {source_file}.")
        return 0

    passing_blocks = []
    retries_used = 0
    for func in functions:
        test_code = generate_tests_for_function(func, source_file, max_retries=max_retries)
        if test_code is None:
            print(f"Could not generate passing tests for {func.name}")
            continue
        passing_blocks.append(test_code)

    module_basename = os.path.splitext(os.path.basename(source_file))[0]
    output_filename = f"test_{module_basename}.py"
    output_path = os.path.join(output_dir, output_filename)

    final_content = _build_imports(source_file) + "\n\n".join(passing_blocks) + "\n"
    with open(output_path, "w") as f:
        f.write(final_content)

    print(
        f"Generated {output_filename} | {len(passing_blocks)} functions tested "
        f"| {retries_used} retries used"
    )

    if coverage:
        print_coverage_summary(source_file, output_path)

    return 0


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    return run(args.source_file, args.coverage, args.max_retries)


if __name__ == "__main__":
    sys.exit(main())

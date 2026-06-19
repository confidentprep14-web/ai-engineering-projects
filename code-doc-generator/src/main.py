"""CLI entry point — extracts public function signatures from a file or
directory, generates LLM-backed markdown docs, and either prints,
writes, or diffs the result against an existing file.
"""

import argparse
import os
import sys

from ast_parser import extract_functions
from differ import print_diff, show_diff
from dotenv import load_dotenv
from generator import generate_module_readme


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate markdown documentation for Python functions via AST + LLM."
    )
    parser.add_argument("target", help="A .py file or a directory to document.")
    parser.add_argument("--output", help="Path to write the generated docs to.")
    parser.add_argument(
        "--diff",
        action="store_true",
        help="Show a diff against --output instead of writing. Requires --output.",
    )
    return parser


def find_python_files(target: str) -> list[str]:
    """Return target itself if it's a .py file, or every .py file found
    recursively under target if it's a directory."""
    if os.path.isfile(target):
        return [target]

    py_files = []
    for root, _dirs, files in os.walk(target):
        for filename in files:
            if filename.endswith(".py"):
                py_files.append(os.path.join(root, filename))
    return sorted(py_files)


def build_docs(py_files: list[str]) -> str:
    """Run extract_functions + generate_module_readme per file and
    concatenate. Files with syntax errors are logged and skipped."""
    sections = []
    for filepath in py_files:
        try:
            functions = extract_functions(filepath)
        except SyntaxError as exc:
            print(f"Skipping {filepath}: {exc}")
            continue

        print(f"Parsed {len(functions)} public functions from {filepath}")
        sections.append(generate_module_readme(filepath, functions))

    return "\n\n---\n\n".join(sections)


def main() -> int:
    load_dotenv()

    parser = build_arg_parser()
    args = parser.parse_args()

    if args.diff and not args.output:
        print("Error: --diff requires --output <path>")
        return 1

    py_files = find_python_files(args.target)
    if not py_files:
        print(f"No Python files found in {args.target}.")
        return 0

    generated = build_docs(py_files)

    if args.diff:
        diff = show_diff(args.output, generated)
        print_diff(diff)
        return 0

    if args.output:
        with open(args.output, "w") as f:
            f.write(generated)
        print(f"Written to {args.output}")
        return 0

    print(generated)
    return 0


if __name__ == "__main__":
    sys.exit(main())

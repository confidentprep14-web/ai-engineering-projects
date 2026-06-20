"""Ground-truth validation of LLM-generated pytest code.

The LLM doesn't execute code — it guesses. The only way to know whether
a generated test is actually correct is to run it with real pytest in a
subprocess and look at the result. This module is the boundary where
"the model said so" becomes "pytest confirmed it."
"""

import os
import re
import subprocess
import sys
import tempfile
import uuid


def _inject_source_path(test_code: str, source_file: str) -> str:
    """Prepend a sys.path insert so the temp test file can import the
    source module regardless of where it's actually written to disk."""
    source_dir = os.path.dirname(os.path.abspath(source_file)) or "."
    header = f"import sys\nsys.path.insert(0, {source_dir!r})\n"
    return header + test_code


def run_pytest_on_generated(test_code: str, source_file: str, func_name: str) -> dict:
    """Write test_code to a temp file and run it with pytest.

    Returns {"passed": bool, "error": str, "output": str}. The temp file
    is always removed, even if pytest itself blows up.
    """
    tmp_dir = tempfile.gettempdir()
    tmp_path = os.path.join(tmp_dir, f"tmp_test_{func_name}_{uuid.uuid4().hex}.py")

    try:
        with open(tmp_path, "w") as f:
            f.write(_inject_source_path(test_code, source_file))

        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", tmp_path, "--tb=short", "-q"],
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            raise RuntimeError("pytest not found — run pip install pytest") from exc

        output = result.stdout + result.stderr
        passed = result.returncode == 0

        if passed:
            return {"passed": True, "error": "", "output": output}

        if "SyntaxError" in output:
            syntax_lines = [line for line in output.splitlines() if "SyntaxError" in line]
            error = syntax_lines[-1] if syntax_lines else "SyntaxError"
            return {"passed": False, "error": error, "output": output}

        tail = "\n".join(output.splitlines()[-20:])
        return {"passed": False, "error": tail, "output": output}
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def parse_pytest_output(output: str) -> dict:
    """Parse a pytest summary line into {"total", "passed", "failed", "errors"}.

    Handles the standard "N passed, M failed" style summary and the
    "no tests ran" case explicitly.
    """
    if "no tests ran" in output:
        return {"total": 0, "passed": 0, "failed": 0, "errors": 1}

    passed = 0
    failed = 0
    errors = 0

    passed_match = re.search(r"(\d+)\s+passed", output)
    if passed_match:
        passed = int(passed_match.group(1))

    failed_match = re.search(r"(\d+)\s+failed", output)
    if failed_match:
        failed = int(failed_match.group(1))

    error_match = re.search(r"(\d+)\s+error", output)
    if error_match:
        errors = int(error_match.group(1))

    total = passed + failed + errors
    return {"total": total, "passed": passed, "failed": failed, "errors": errors}


def _split_test_functions(test_code: str) -> tuple[str, list[str]]:
    """Split a combined test file into (preamble, [test function blocks]).

    The preamble is everything before the first `def test_` (imports,
    sys.path setup, etc). Each block starts at its `def test_` line and
    runs until the next top-level `def test_` or end of file.
    """
    lines = test_code.splitlines(keepends=True)
    test_starts = [i for i, line in enumerate(lines) if line.startswith("def test_")]

    if not test_starts:
        return test_code, []

    preamble = "".join(lines[: test_starts[0]])
    blocks = []
    for idx, start in enumerate(test_starts):
        end = test_starts[idx + 1] if idx + 1 < len(test_starts) else len(lines)
        blocks.append("".join(lines[start:end]))
    return preamble, blocks


def filter_passing_tests(all_test_code: str, source_file: str) -> str:
    """Run each `def test_*` block individually against source_file and
    reassemble a file containing only the ones that actually pass.

    This is the guarantee step: instead of trusting the whole generated
    file to pass, each test function is isolated and proven independently.
    """
    preamble, blocks = _split_test_functions(all_test_code)

    passing_blocks = []
    for block in blocks:
        func_name_match = re.match(r"def (test_\w+)", block)
        func_name = func_name_match.group(1) if func_name_match else "unknown"

        candidate = preamble + "\n" + block
        result = run_pytest_on_generated(candidate, source_file, func_name)
        if result["passed"]:
            passing_blocks.append(block)

    return preamble + "\n" + "\n".join(passing_blocks)


def print_coverage_summary(source_file: str, test_file: str) -> None:
    """Run pytest-cov against source_file using test_file and print the
    coverage report (including a TOTAL line with a percentage) to stdout."""
    source_module = os.path.splitext(os.path.basename(source_file))[0]
    source_dir = os.path.dirname(os.path.abspath(source_file)) or "."

    env = os.environ.copy()
    env["PYTHONPATH"] = source_dir + os.pathsep + env.get("PYTHONPATH", "")

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                test_file,
                f"--cov={source_module}",
                "--cov-report=term-missing",
                "-q",
            ],
            capture_output=True,
            text=True,
            cwd=source_dir,
            env=env,
        )
    except OSError as exc:
        raise RuntimeError("pytest not found — run pip install pytest") from exc

    output = result.stdout + result.stderr
    print(output)

    total_line = next((line for line in output.splitlines() if line.startswith("TOTAL")), None)
    if total_line:
        match = re.search(r"(\d+)%", total_line)
        if match:
            print(f"Branch/line coverage: {match.group(1)}%")

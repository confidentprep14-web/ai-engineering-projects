"""SQL safety validation via the sqlglot AST — not regex.

Regex cannot parse SQL reliably: a query like
SELECT name FROM (SELECT * FROM users WHERE type='DROP TABLE')
contains the string "DROP TABLE" as a literal, which a regex-based
blocklist would falsely flag. Parsing into an AST and checking the node
type is the only reliable way to tell SELECT from everything else.
"""

from dataclasses import dataclass

import sqlglot
import sqlglot.errors


@dataclass
class ValidationResult:
    is_valid: bool
    error: str | None  # Human-readable error if not valid
    statement_type: str | None  # "SELECT", "INSERT", etc.


def parse_and_validate(sql: str) -> ValidationResult:
    """Parse `sql` with sqlglot and ensure it is a single SELECT statement."""
    try:
        parsed = sqlglot.parse_one(sql)
    except sqlglot.errors.ParseError as e:
        return ValidationResult(is_valid=False, error=f"SQL parse error: {e}", statement_type=None)

    stmt_type = type(parsed).__name__
    if stmt_type != "Select":
        return ValidationResult(
            is_valid=False,
            error=f"Only SELECT queries are allowed. Got: {stmt_type}.",
            statement_type=stmt_type,
        )

    return ValidationResult(is_valid=True, error=None, statement_type="SELECT")


def extract_sql_from_response(response: str) -> str:
    """Strip markdown code fences and extra statements from a raw LLM response."""
    text = response.strip()

    if text.startswith("```"):
        lines = text.splitlines()
        # Drop the opening fence line (``` or ```sql)
        lines = lines[1:]
        # Drop the closing fence line if present
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # If multiple statements are present, take only the first.
    text = text.split(";")[0].strip()

    return text

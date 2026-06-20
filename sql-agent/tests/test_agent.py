"""Tests for src/agent.py — retry loop and result interpretation.

nl_to_sql, execute_safe, and get_completion are the only functions that
touch the LLM or a live database; they're mocked here per spec Test 4 and
Test 6. retry_on_error's control flow (validate -> execute -> retry on
error, injecting the prior error into the next prompt) is real logic
under test.
"""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import agent  # noqa: E402
from agent import interpret_results, retry_on_error  # noqa: E402


def test_retry_injects_sql_error_into_next_prompt():
    """Spec test 4: execute_safe fails once with a column error, succeeds on
    the second attempt; nl_to_sql must be called twice, and the second call's
    prior_error must surface the original error message."""
    call_args = []

    def fake_nl_to_sql(question, schema_str, prior_error=""):
        call_args.append({"question": question, "schema_str": schema_str, "prior_error": prior_error})
        return "SELECT * FROM customers"

    execute_safe_calls = {"count": 0}

    def fake_execute_safe(sql, db_path):
        execute_safe_calls["count"] += 1
        if execute_safe_calls["count"] == 1:
            raise RuntimeError("no such column: foo")
        return [{"id": 1, "name": "Alice"}], ["id", "name"]

    with patch("agent.nl_to_sql", side_effect=fake_nl_to_sql), patch(
        "agent.execute_safe", side_effect=fake_execute_safe
    ):
        rows, column_names, sql_used, attempts = retry_on_error(
            "Show me all customers", "Tables:\n\ncustomers (...)", "ecommerce.db", max_retries=2
        )

    assert len(call_args) == 2
    assert call_args[1]["prior_error"] is not None
    assert "no such column" in call_args[1]["prior_error"]
    assert rows == [{"id": 1, "name": "Alice"}]
    assert attempts == 2


def test_retry_raises_after_exhausting_retries():
    def always_fails(sql, db_path):
        raise RuntimeError("no such table: ghosts")

    with patch("agent.nl_to_sql", return_value="SELECT * FROM ghosts"), patch(
        "agent.execute_safe", side_effect=always_fails
    ):
        try:
            retry_on_error("Show me ghosts", "Tables:\n\ncustomers (...)", "ecommerce.db", max_retries=2)
            assert False, "expected RuntimeError"
        except RuntimeError as e:
            assert "2 attempts" in str(e)


def test_retry_treats_invalid_sql_as_prior_error_without_executing():
    """An invalid (non-SELECT) generation should retry via parse_and_validate's
    error, never reaching execute_safe on that attempt."""
    nl_to_sql_calls = []

    def fake_nl_to_sql(question, schema_str, prior_error=""):
        nl_to_sql_calls.append(prior_error)
        if len(nl_to_sql_calls) == 1:
            return "DELETE FROM customers"
        return "SELECT * FROM customers"

    with patch("agent.nl_to_sql", side_effect=fake_nl_to_sql), patch(
        "agent.execute_safe", return_value=([{"id": 1}], ["id"])
    ) as mock_execute:
        rows, column_names, sql_used, attempts = retry_on_error(
            "Show me all customers", "Tables:\n\ncustomers (...)", "ecommerce.db", max_retries=2
        )

    assert len(nl_to_sql_calls) == 2
    assert "Only SELECT" in nl_to_sql_calls[1]
    assert mock_execute.call_count == 1  # only called on the valid attempt
    assert sql_used == "SELECT * FROM customers"


def test_interpret_results_empty_rows_skips_llm_call():
    """Spec test 6: empty results short-circuit without calling get_completion."""
    with patch("agent.get_completion") as mock_get_completion:
        result = interpret_results("How many?", rows=[], column_names=["count"])

    assert result == "No results found."
    mock_get_completion.assert_not_called()


def test_interpret_results_non_empty_calls_llm():
    with patch("agent.get_completion", return_value="There are 3 customers from the US.") as mock_get_completion:
        result = interpret_results(
            "How many customers are from the US?",
            rows=[{"count": 3}],
            column_names=["count"],
        )

    mock_get_completion.assert_called_once()
    assert result == "There are 3 customers from the US."

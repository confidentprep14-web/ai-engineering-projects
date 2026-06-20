"""Exercises src/config.get_llm_api_key() without ever calling AWS.

The Secrets Manager branch only activates when AWS_LAMBDA_FUNCTION_NAME is
set (i.e. actually running inside Lambda). Locally and in CI that variable
is absent, so get_llm_api_key() must fall back to LLM_API_KEY from the
environment. We also verify the Lambda branch reaches boto3 by mocking the
client — this confirms the *wiring*, not a real AWS call.
"""
import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("DATABASE_PATH", "/tmp/test_config_chat_requests.db")

from src.config import get_llm_api_key  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    monkeypatch.delenv("SECRET_NAME", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)


def test_falls_back_to_env_var_when_not_on_lambda(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-local-test-key")

    assert get_llm_api_key() == "sk-local-test-key"


def test_returns_empty_string_when_no_env_var_and_not_on_lambda():
    assert get_llm_api_key() == ""


def test_ignores_secret_name_when_not_running_on_lambda(monkeypatch):
    """SECRET_NAME alone must not trigger a Secrets Manager call — only the
    combination of SECRET_NAME *and* AWS_LAMBDA_FUNCTION_NAME should."""
    monkeypatch.setenv("SECRET_NAME", "chat-api/llm-api-key")
    monkeypatch.setenv("LLM_API_KEY", "sk-local-fallback")

    assert get_llm_api_key() == "sk-local-fallback"


def test_reads_from_secrets_manager_when_on_lambda(monkeypatch):
    """When both AWS_LAMBDA_FUNCTION_NAME and SECRET_NAME are set, the
    function must go through boto3's secretsmanager client instead of the
    env var. The boto3 call itself is mocked — this is an AWS infra call,
    not an LLM provider call, so mocking it here does not violate the
    no-mocked-LLM-calls rule."""
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "chat-api-lambda")
    monkeypatch.setenv("SECRET_NAME", "chat-api/llm-api-key")
    monkeypatch.setenv("LLM_API_KEY", "sk-should-not-be-used")

    mock_client = MagicMock()
    mock_client.get_secret_value.return_value = {
        "SecretString": '{"LLM_API_KEY": "sk-from-secrets-manager"}'
    }

    with patch("boto3.client", return_value=mock_client) as mock_boto3_client:
        result = get_llm_api_key()

    assert result == "sk-from-secrets-manager"
    mock_boto3_client.assert_called_once_with("secretsmanager", region_name="us-east-1")
    mock_client.get_secret_value.assert_called_once_with(SecretId="chat-api/llm-api-key")

"""Central configuration loaded once from environment variables.

Every other module reads settings through this object instead of calling
os.getenv() directly, so there is exactly one place that knows the env var
names and their defaults. On Lambda, DATABASE_PATH and INDEX_PATH default
to /tmp — the only writable filesystem path in the Lambda execution
environment — and the LLM API key is read from Secrets Manager instead of
a plaintext env var (same pattern as aws-lambda-deploy/src/config.py).
"""
import json
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def get_llm_api_key() -> str:
    """Read LLM API key from Secrets Manager when running on Lambda, else from env.

    AWS_LAMBDA_FUNCTION_NAME is set automatically by the Lambda runtime, so its
    presence is what distinguishes "running on Lambda" from local/test runs —
    we never want a local pytest run or `docker compose up` to attempt a real
    Secrets Manager call.
    """
    secret_name = os.getenv("SECRET_NAME")
    if secret_name and os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        import boto3

        client = boto3.client("secretsmanager", region_name=os.getenv("AWS_REGION", "us-east-1"))
        secret = client.get_secret_value(SecretId=secret_name)
        return json.loads(secret["SecretString"])["LLM_API_KEY"]
    return os.getenv("LLM_API_KEY", "")


@dataclass
class Config:
    llm_provider: str = os.getenv("LLM_PROVIDER", "anthropic")
    llm_model: str = os.getenv("LLM_MODEL", "claude-3-5-haiku-20241022")
    llm_api_key: str = ""
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    database_path: str = os.getenv("DATABASE_PATH", "/tmp/assistant.db")
    index_path: str = os.getenv("INDEX_PATH", "/tmp/rag_index")
    rate_limit_requests_per_minute: int = int(os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "20"))
    cost_per_1m_input_tokens: float = float(os.getenv("COST_PER_1M_INPUT_TOKENS", "1.00"))
    cost_per_1m_output_tokens: float = float(os.getenv("COST_PER_1M_OUTPUT_TOKENS", "5.00"))
    max_context_tokens: int = int(os.getenv("MAX_CONTEXT_TOKENS", "8192"))
    context_strategy: str = os.getenv("CONTEXT_STRATEGY", "sliding")
    rag_top_k: int = int(os.getenv("RAG_TOP_K", "3"))
    rag_score_threshold: float = float(os.getenv("RAG_SCORE_THRESHOLD", "0.3"))
    max_tool_iterations: int = int(os.getenv("MAX_TOOL_ITERATIONS", "8"))
    max_upload_bytes: int = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))

    def __post_init__(self) -> None:
        self.llm_api_key = get_llm_api_key()


config = Config()

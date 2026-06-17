"""Central configuration loaded once from environment variables.

Every other module reads settings through this object instead of calling
os.getenv() directly, so there is exactly one place that knows the env var
names and their defaults.
"""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    llm_provider: str = os.getenv("LLM_PROVIDER", "anthropic")
    llm_model: str = os.getenv("LLM_MODEL", "claude-3-5-haiku-20241022")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    rate_limit_requests_per_minute: int = int(
        os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "20")
    )
    cost_per_1m_input_tokens: float = float(os.getenv("COST_PER_1M_INPUT_TOKENS", "1.00"))
    cost_per_1m_output_tokens: float = float(os.getenv("COST_PER_1M_OUTPUT_TOKENS", "5.00"))
    database_path: str = os.getenv("DATABASE_PATH", "./chat_requests.db")


config = Config()

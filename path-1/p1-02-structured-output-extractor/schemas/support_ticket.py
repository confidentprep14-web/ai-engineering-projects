from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class SupportTicket(BaseModel):
    """Structured fields extracted from a free-text customer support complaint."""

    model_config = ConfigDict(extra="ignore")

    customer_name: Optional[str] = None
    product: str
    issue_summary: str  # one sentence max
    severity: Literal["low", "medium", "high", "critical"]
    steps_to_reproduce: list[str]  # empty list if not provided
    requested_resolution: Optional[str] = None

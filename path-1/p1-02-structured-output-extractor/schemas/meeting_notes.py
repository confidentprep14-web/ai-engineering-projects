from typing import Optional

from pydantic import BaseModel, ConfigDict


class ActionItem(BaseModel):
    """A single action item assigned during a meeting."""

    model_config = ConfigDict(extra="ignore")

    owner: str
    task: str
    due_date: Optional[str] = None  # ISO date string or None


class MeetingNotes(BaseModel):
    """Structured fields extracted from a free-text meeting transcript."""

    model_config = ConfigDict(extra="ignore")

    meeting_title: str
    date: Optional[str] = None
    attendees: list[str]
    decisions: list[str]  # concrete decisions made
    action_items: list[ActionItem]

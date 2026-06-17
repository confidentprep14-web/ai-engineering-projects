from typing import Optional

from pydantic import BaseModel, ConfigDict


class JobPosting(BaseModel):
    """Structured fields extracted from a free-text job posting."""

    model_config = ConfigDict(extra="ignore")

    job_title: str
    company_name: str
    location: str  # "Remote", "New York, NY", etc.
    employment_type: str  # "Full-time", "Contract", "Part-time"
    required_skills: list[str]  # at least 1 item
    years_experience_required: Optional[int] = None  # None if not stated
    salary_range: Optional[str] = None  # None if not stated

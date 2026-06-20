"""Loaders for GitHub issue JSON / ADR markdown, and LLM-backed decision
extraction.

load_github_issue_json() and load_adr_markdown() are pure parsing —
no LLM call. extract_decision() is the only function that calls the LLM
boundary (get_json_completion); unit tests mock that call directly so the
loaders and the dataclass-construction logic are exercised without an
API key. The real CLI path (src/main.py --extract) calls a live provider.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import date
from uuid import uuid4

from llm import get_json_completion

SYSTEM_PROMPT = (
    "You are an engineering knowledge curator. Extract the key architectural "
    "or process decision from this document. Return JSON with: decision (one "
    "sentence), rationale (2-3 sentences), author (if identifiable, else "
    "'unknown'), tags (list of 3-5 topic keywords), date (ISO date if found, "
    "else null)."
)

_TITLE_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_DATE_RE = re.compile(r"^Date:\s*(\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE)


@dataclass
class Decision:
    id: str
    date: str
    decision: str
    rationale: str
    author: str
    tags: list[str] = field(default_factory=list)
    source_file: str = ""
    source_type: str = ""
    raw_title: str = ""


def load_github_issue_json(filepath: str) -> dict:
    """Load a GitHub issue export JSON file.

    Returns a dict with number/title/body/comments/closed_at, defaulting
    missing keys to empty values. Raises ValueError (with filepath) if the
    file is not valid JSON.
    """
    with open(filepath, encoding="utf-8") as f:
        raw_text = f.read()

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {filepath}: {exc}") from exc

    return {
        "number": data.get("number", ""),
        "title": data.get("title", ""),
        "body": data.get("body", ""),
        "comments": data.get("comments") or [],
        "closed_at": data.get("closed_at", ""),
    }


def load_adr_markdown(filepath: str) -> dict:
    """Load an ADR markdown file.

    Returns {"title": str, "date": str | None, "content": str}. Falls back
    to the filename when no '# Title' heading is found, and to None when
    no 'Date: YYYY-MM-DD' line is found.
    """
    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    title_match = _TITLE_RE.search(content)
    title = title_match.group(1).strip() if title_match else _basename(filepath)

    date_match = _DATE_RE.search(content)
    found_date = date_match.group(1) if date_match else None

    return {"title": title, "date": found_date, "content": content}


def _basename(filepath: str) -> str:
    return filepath.replace("\\", "/").rsplit("/", 1)[-1]


def _build_prompt(raw_content: dict, source_type: str) -> str:
    if source_type == "adr":
        return f"ADR document:\n\n{raw_content.get('content', '')}"

    title = raw_content.get("title", "")
    body = raw_content.get("body", "")
    comments = raw_content.get("comments") or []
    comment_text = "\n".join(f"- {c.get('body', '')}" for c in comments)
    return (
        f"GitHub issue title: {title}\n\n"
        f"Issue body:\n{body}\n\n"
        f"Comments:\n{comment_text}"
    )


def _normalize_tags(raw_tags) -> list[str]:
    if raw_tags is None:
        return []
    if isinstance(raw_tags, str):
        return [t.strip() for t in raw_tags.split(",") if t.strip()]
    if isinstance(raw_tags, list):
        return [str(t) for t in raw_tags]
    return []


def extract_decision(raw_content: dict, source_type: str, source_file: str) -> Decision:
    """Call the LLM to extract a structured Decision from loaded content.

    raw_content comes from load_github_issue_json (source_type="github_issue")
    or load_adr_markdown (source_type="adr"). Falls back to the raw title
    when the LLM returns a null/empty decision, and to closed_at / today's
    date when the LLM does not supply a date.
    """
    prompt = _build_prompt(raw_content, source_type)
    result = get_json_completion(prompt, system=SYSTEM_PROMPT)

    raw_title = raw_content.get("title", source_file)

    decision_text = result.get("decision") or raw_content.get("title", "Unknown decision")
    rationale = result.get("rationale") or ""
    author = result.get("author") or "unknown"
    tags = _normalize_tags(result.get("tags"))

    extracted_date = result.get("date")
    if not extracted_date:
        extracted_date = raw_content.get("closed_at") or raw_content.get("date")
    if extracted_date:
        # Trim a full ISO datetime (e.g. closed_at) down to just the date.
        extracted_date = str(extracted_date)[:10]
    else:
        extracted_date = date.today().isoformat()

    return Decision(
        id=uuid4().hex[:12],
        date=extracted_date,
        decision=decision_text,
        rationale=rationale,
        author=author,
        tags=tags,
        source_file=source_file,
        source_type=source_type,
        raw_title=raw_title,
    )

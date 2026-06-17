# Structured Output Extractor

Extracts structured data from unstructured text — job postings, meeting notes,
support tickets — into validated Pydantic objects, with automatic retry when
the LLM returns malformed JSON.

## What this is

LLM output is untrusted input: it can arrive as near-JSON, JSON wrapped in a
markdown code fence, or JSON missing fields your schema requires. This project
treats every completion as untrusted, validates it against a Pydantic model,
and on failure feeds the exact validation error back into the next prompt so
the model has a concrete reason to fix its output. Each document gets up to
`MAX_RETRIES` attempts before extraction is reported as a failure.

## Setup

```bash
cd p1-02-structured-output-extractor
cp .env.example .env
# Edit .env: set LLM_PROVIDER and LLM_API_KEY
pip install -r requirements.txt
```

## Run

```bash
# Single file — schema inferred from filename
python src/main.py sample_inputs/job_posting.txt

# Explicit schema
python src/main.py my_notes.txt --schema meeting_notes

# Batch mode
python src/main.py "sample_inputs/*.txt" --schema job_posting --batch
```

Expected output (single file):
```
Extracting job posting from sample_inputs/job_posting.txt...
Attempts used: 1

{
  "job_title": "Senior ML Engineer",
  "company_name": "Acme Corp",
  "location": "Remote",
  "employment_type": "Full-time",
  "required_skills": ["Python", "PyTorch", "AWS"],
  "years_experience_required": 5,
  "salary_range": "$180,000-$220,000"
}
```

## Tests

```bash
pytest tests/ -v
```

Tests verify retry logic, JSON fence stripping, and Pydantic validation — no API key required.

## What to try next

- Add a new schema (e.g. invoice, resume) by creating a Pydantic model in `schemas/`
- Log the token cost of each extraction call
- Stream extracted fields as they are confirmed valid

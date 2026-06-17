import argparse
import glob
import json
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extractor import ExtractionError, batch_extract, extract
from schemas.job_posting import JobPosting
from schemas.meeting_notes import MeetingNotes
from schemas.support_ticket import SupportTicket

SCHEMA_REGISTRY = {
    "job_posting": (JobPosting, "job posting"),
    "meeting_notes": (MeetingNotes, "meeting notes"),
    "support_ticket": (SupportTicket, "support ticket"),
}


def infer_schema_name(file_path: str) -> str | None:
    """Guess the schema name from the filename, e.g. 'job_posting.txt' -> 'job_posting'."""
    file_name = os.path.basename(file_path).lower()
    for schema_name in SCHEMA_REGISTRY:
        if schema_name in file_name:
            return schema_name
    return None


def resolve_schema_name(file_paths: list[str], explicit_schema_name: str | None) -> str:
    if explicit_schema_name:
        return explicit_schema_name

    inferred_schema_name = infer_schema_name(file_paths[0])
    if inferred_schema_name is None:
        print(
            "Could not infer schema from filename. Pass --schema "
            f"{{{'|'.join(SCHEMA_REGISTRY)}}}."
        )
        sys.exit(1)
    return inferred_schema_name


def run_single_file(file_path: str, schema_class, document_type: str) -> None:
    if not os.path.isfile(file_path):
        print(f"File not found: {file_path}")
        sys.exit(1)

    with open(file_path, "r", encoding="utf-8") as input_file:
        document_text = input_file.read()

    print(f"Extracting {document_type} from {file_path}...")
    try:
        validated_object, attempts_used = extract(document_text, schema_class, document_type)
    except ExtractionError as extraction_error:
        print(f"Extraction failed: {extraction_error}")
        sys.exit(1)

    print(f"Attempts used: {attempts_used}\n")
    print(json.dumps(validated_object.model_dump(), indent=2))


def run_batch(file_paths: list[str], schema_class, document_type: str) -> None:
    existing_file_paths = []
    for file_path in file_paths:
        if os.path.isfile(file_path):
            existing_file_paths.append(file_path)
        else:
            print(f"File not found, skipping: {file_path}")

    if not existing_file_paths:
        print("No valid files to process.")
        sys.exit(1)

    batch_summary = batch_extract(existing_file_paths, schema_class, document_type)
    total_documents = batch_summary["successes"] + batch_summary["failures"]
    average_attempts = (
        batch_summary["total_attempts"] / total_documents if total_documents else 0.0
    )

    print(
        f"Extraction: {batch_summary['successes']}/{total_documents} succeeded | "
        f"Avg attempts: {average_attempts:.1f} | "
        f"Total LLM calls: {batch_summary['total_attempts']}"
    )
    for result in batch_summary["results"]:
        print(f"  {result['file']}: {result['status']}")


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Extract structured data from unstructured text.")
    parser.add_argument("file_or_glob", help="Path or glob pattern of input file(s)")
    parser.add_argument(
        "--schema",
        choices=list(SCHEMA_REGISTRY),
        default=None,
        help="Schema to validate against. Inferred from filename if omitted.",
    )
    parser.add_argument("--batch", action="store_true", help="Process all matched files as a batch")
    parsed_args = parser.parse_args()

    matched_file_paths = sorted(glob.glob(parsed_args.file_or_glob)) or [parsed_args.file_or_glob]
    schema_name = resolve_schema_name(matched_file_paths, parsed_args.schema)
    schema_class, document_type = SCHEMA_REGISTRY[schema_name]

    if parsed_args.batch or len(matched_file_paths) > 1:
        run_batch(matched_file_paths, schema_class, document_type)
    else:
        run_single_file(matched_file_paths[0], schema_class, document_type)


if __name__ == "__main__":
    main()

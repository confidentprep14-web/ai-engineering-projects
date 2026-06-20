"""String utility functions used as a fixture for test generation."""


def truncate(text: str, length: int = 10) -> str:
    """Truncate text to length characters, appending '...' if shortened."""
    if len(text) <= length:
        return text
    return text[:length] + "..."


def slugify(text: str) -> str:
    """Convert text to a URL-friendly slug."""
    return "-".join(text.lower().split())


def count_words(text: str) -> int:
    """Count the number of whitespace-separated words in text."""
    return len(text.split())

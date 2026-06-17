from pathlib import Path


def load_document(file_path: str) -> list[dict]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Cannot open {file_path} — check the path")

    extension = path.suffix.lower()
    if extension == ".pdf":
        return _load_pdf(path)
    if extension == ".txt":
        return _load_txt(path)
    raise ValueError(f"Only .pdf and .txt supported, got {extension}")


def _load_pdf(path: Path) -> list[dict]:
    import pdfplumber

    pages = []
    with pdfplumber.open(path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if not text:
                continue
            pages.append({"page": page_number, "text": text, "source": path.name})
    return pages


def _load_txt(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    return [{"page": 1, "text": text, "source": path.name}]

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from chunker import ast_chunk_python, file_hash, heuristic_chunk

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
SAMPLE_MODULE = str(FIXTURES_DIR / "sample_module.py")
SAMPLE_CONFIG = str(FIXTURES_DIR / "sample_config.yaml")


def test_ast_chunker_extracts_function_boundaries():
    chunks = ast_chunk_python(SAMPLE_MODULE)

    assert len(chunks) == 5
    for chunk in chunks:
        assert "function_name" in chunk
        assert "lineno" in chunk
        assert "end_lineno" in chunk
        assert "text" in chunk
        assert not chunk["function_name"].startswith("__")


def test_heuristic_chunker_handles_non_python_files():
    chunks = heuristic_chunk(SAMPLE_CONFIG)

    assert len(chunks) >= 1
    for chunk in chunks:
        assert "lineno" in chunk
        assert "text" in chunk
        assert chunk["function_name"].startswith("chunk_")


def test_file_hash_changes_when_content_changes(tmp_path):
    original_hash = file_hash(SAMPLE_MODULE)

    modified_file = tmp_path / "modified_module.py"
    original_content = Path(SAMPLE_MODULE).read_text()
    modified_file.write_text(original_content + "\n# a trailing comment\n")

    modified_hash = file_hash(str(modified_file))

    assert original_hash != modified_hash


def test_ast_chunker_handles_syntax_error_gracefully(tmp_path):
    broken_file = tmp_path / "broken.py"
    broken_file.write_text("def broken(:\n    this is not valid python\n")

    chunks = ast_chunk_python(str(broken_file))

    assert chunks == []

# Build Guide — Docs Copilot

## Step 1 — Metadata-aware chunking

The key difference from basic RAG: preserve the section heading with every chunk.

```python
def markdown_chunk_by_section(filepath):
    content = open(filepath).read()
    lines = content.splitlines()

    current_heading = os.path.basename(filepath).replace(".md", "")
    current_lines = []
    chunks = []

    for line in lines:
        if line.startswith("#"):
            if current_lines:
                text = "\n".join(current_lines).strip()
                meta = ChunkMetadata(
                    doc_title=os.path.basename(filepath).replace(".md", ""),
                    section_heading=current_heading,
                    last_modified=os.path.getmtime(filepath),
                    source_file=filepath,
                    chunk_index=len(chunks),
                    char_count=len(text),
                )
                chunks.append((text, meta))
                current_lines = []
            current_heading = line.lstrip("#").strip()
        else:
            current_lines.append(line)

    # Don't forget the last section
    if current_lines:
        ...

    return chunks
```

## Step 2 — Freshness tracking

Store mtimes, not content hashes. Mtime is cheaper to read than hashing:

```python
import os, json

def check_freshness(index_dir, docs_dir):
    stored = json.load(open(f"{index_dir}/file_mtimes.json"))
    for filepath in walk_docs(docs_dir):
        current_mtime = os.path.getmtime(filepath)
        if stored.get(filepath) != current_mtime:
            return True   # stale
    return False
```

## Step 3 — The confidence gate

Check the top retrieval score BEFORE calling the LLM:

```python
results = search_with_metadata(query, model, index, chunks, top_k)
top_score = results[0]["score"] if results else 0.0

if top_score < CONFIDENCE_THRESHOLD:
    print(handle_below_threshold(query, top_score, CONFIDENCE_THRESHOLD))
    return
```

This saves an LLM call and avoids hallucination on topics not covered by the docs.

## Step 4 — Citations in the prompt

Format context so the LLM knows the source of each chunk:

```
[Source: setup_guide > Database Configuration]
To configure the database, set DATABASE_URL in your .env file...

[Source: api_reference > Authentication]
All API calls require a Bearer token in the Authorization header...
```

Instruct the LLM: "After each claim, cite the source in [source > section] format."

## Step 5 — Remembering which directory was indexed

`--ask` needs to re-run the freshness check without the caller repeating which
directory was indexed. Rather than expanding `file_mtimes.json`'s schema, write
the docs directory path to a small sidecar file (`.index/docs_dir.txt`) when
`--index <dir>` runs, and read it back on `--ask`. Keeps `indexer.py`'s
already-tested save/load contract untouched.

## Debugging tips

- If citations are missing, check that the system prompt explicitly requires them
- If freshness check always triggers, verify mtime comparison uses `==` not `is`
- If PDF chunks are empty, use `pdfplumber` — not PyPDF2 — for better text extraction
- **If the test process segfaults (exit code 139) even though pytest already printed `N passed`**: on some local Python builds (observed with an Anaconda-based Python 3.12 install on macOS), importing `torch` + `faiss-cpu` + `sentence-transformers` together in one process triggers a native crash during interpreter shutdown — after the test results are already correct and printed, not during the tests themselves. `HF_HUB_OFFLINE=1` and `KMP_DUPLICATE_LIB_OK=TRUE` were both tried and neither prevents it; this looks like an OpenMP/native-library teardown conflict between torch and faiss on this platform, not a bug in this project's code. Trust the printed `passed`/`failed` summary over the shell exit code if this happens — don't assume a 139 means the suite failed without checking the actual output first.

## How to talk about this in an interview

**"How is this different from the RAG you built in Path 1?"**
> Three differences. First, I chunk by section heading instead of fixed size — this gives more semantically coherent chunks. Second, I attach metadata (doc title, section, mtime) to every chunk so citations are reliable. Third, I gate on a confidence threshold — if retrieval scores are below the threshold, I return 'I don't know' rather than risk hallucination.

**"How does freshness tracking work?"**
> I store the mtime of each indexed file alongside the index. On every `--ask`, I check current mtimes against stored ones. If any file changed, I re-index it before answering. This means the index is always current without requiring manual rebuilds.

**"What threshold do you use and how did you choose it?"**
> I use 0.5 on the inner product of L2-normalized vectors (equivalent to cosine similarity). I tuned it by asking 10 questions I knew the docs covered and 10 I knew they didn't, and found 0.5 gave zero false "I know" responses on the second set.

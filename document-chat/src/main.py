import argparse
import os
import time

from dotenv import load_dotenv

from chunker import chunk_document, retrieve_top_chunks
from llm import stream_completion
from loader import load_document


def build_prompt(question: str, retrieved_chunks: list[dict]) -> str:
    context_lines = [
        f"[Chunk {chunk['chunk_index']}, chars {chunk['char_start']}–{chunk['char_end']}]: {chunk['text']}"
        for chunk in retrieved_chunks
    ]
    context = "\n".join(context_lines)
    return (
        "Answer the question using ONLY the context below.\n"
        "Cite sources as [Chunk N, chars X–Y].\n"
        'If the answer is not in the context, say "Not found in document."\n\n'
        f"Context:\n{context}\n\n"
        f"Question: {question}"
    )


def answer_question(question: str, chunks: list[dict], top_k: int) -> None:
    t_start = time.perf_counter()
    retrieved_chunks = retrieve_top_chunks(question, chunks, top_k)
    prompt = build_prompt(question, retrieved_chunks)

    print("\nAnswer:\n")
    t_first_token = None
    for token in stream_completion(prompt):
        if t_first_token is None:
            t_first_token = time.perf_counter()
        print(token, end="", flush=True)
    t_end = time.perf_counter()
    print()

    first_token_ms = (t_first_token - t_start) * 1000 if t_first_token else 0
    total_ms = (t_end - t_start) * 1000
    print(f"\n⏱  First token: {first_token_ms:.0f}ms | Total: {total_ms:.0f}ms")


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Chat with a document via chunked retrieval.")
    parser.add_argument("file_path")
    parser.add_argument("--question", default=None)
    parser.add_argument("--chunk-size", type=int, default=int(os.environ.get("CHUNK_SIZE", 1000)))
    parser.add_argument("--overlap", type=int, default=int(os.environ.get("CHUNK_OVERLAP", 200)))
    parser.add_argument("--top-k", type=int, default=int(os.environ.get("TOP_K_CHUNKS", 3)))
    args = parser.parse_args()

    pages = load_document(args.file_path)
    print(f"Loaded {len(pages)} pages from {args.file_path}")

    chunks = chunk_document(pages, args.chunk_size, args.overlap)
    print(f"Created {len(chunks)} chunks (size={args.chunk_size}, overlap={args.overlap})")

    if args.question:
        answer_question(args.question, chunks, args.top_k)
        return

    print("Ask a question (or 'quit'):")
    while True:
        question = input("> ")
        if question.strip().lower() == "quit":
            break
        answer_question(question, chunks, args.top_k)


if __name__ == "__main__":
    main()

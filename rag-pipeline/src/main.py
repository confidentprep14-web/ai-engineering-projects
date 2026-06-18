import argparse
import os
import sys

from dotenv import load_dotenv

from embedder import load_embedding_model
from indexer import build_index, load_index
from rag import answer_with_rag, answer_without_rag

DEFAULT_INDEX_DIR = ".index"


def _format_score_list(retrieved_chunks: list[dict]) -> str:
    return ", ".join(f"{chunk['score']:.2f}" for chunk in retrieved_chunks)


def run_rag_query(query: str, index_dir: str, embedding_model) -> dict:
    faiss_index, chunk_metadata = load_index(index_dir)
    rag_result = answer_with_rag(query, faiss_index, chunk_metadata, embedding_model)

    if rag_result["chunks_retrieved"] > 0:
        top_score = rag_result["sources"][0]["score"]
        print(f"Retrieved {rag_result['chunks_retrieved']} chunks (scores: {_format_score_list(rag_result['sources'])})")
    else:
        top_score = 0.0
        print("Retrieved 0 chunks above threshold")

    print(f"\nAnswer:\n{rag_result['answer']}")
    print(
        f"\n⏱  Retrieval: {rag_result['retrieval_ms']:.0f}ms (top score: {top_score:.2f}) "
        f"| Generation: {rag_result['generation_ms']:.0f}ms"
    )
    return rag_result


def run_ab_comparison(query: str, index_dir: str, embedding_model) -> None:
    faiss_index, chunk_metadata = load_index(index_dir)
    rag_result = answer_with_rag(query, faiss_index, chunk_metadata, embedding_model)
    no_rag_result = answer_without_rag(query)

    print("=" * 70)
    print("WITH RAG")
    print("=" * 70)
    print(rag_result["answer"])
    if rag_result["chunks_retrieved"] > 0:
        print(f"\nSources: {_format_score_list(rag_result['sources'])}")
    print(f"⏱  Retrieval: {rag_result['retrieval_ms']:.0f}ms | Generation: {rag_result['generation_ms']:.0f}ms")

    print()
    print("=" * 70)
    print("WITHOUT RAG")
    print("=" * 70)
    print(no_rag_result["answer"])
    print(f"⏱  Generation: {no_rag_result['generation_ms']:.0f}ms")


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="RAG pipeline over a folder of documents.")
    parser.add_argument("--index", dest="doc_dir", default=None, help="Build index from this directory")
    parser.add_argument("--query", default=None, help="Answer a question using the existing index")
    parser.add_argument("--ab", default=None, help="Compare RAG vs no-RAG answers for a question")
    parser.add_argument("--reindex", action="store_true", help="Force rebuild even if an index exists")
    args = parser.parse_args()

    index_dir = DEFAULT_INDEX_DIR
    chunk_size = int(os.environ.get("CHUNK_SIZE", 800))
    chunk_overlap = int(os.environ.get("CHUNK_OVERLAP", 150))

    index_already_exists = os.path.isfile(os.path.join(index_dir, "index.faiss"))

    try:
        if args.doc_dir:
            if index_already_exists and not args.reindex:
                print(f"Index already exists at {index_dir}/ — pass --reindex to force a rebuild")
            else:
                embedding_model = load_embedding_model()
                build_index(args.doc_dir, index_dir, embedding_model, chunk_size, chunk_overlap)
            if not args.query and not args.ab:
                return

        if args.query:
            embedding_model = load_embedding_model()
            run_rag_query(args.query, index_dir, embedding_model)
            return

        if args.ab:
            embedding_model = load_embedding_model()
            run_ab_comparison(args.ab, index_dir, embedding_model)
            return

        embedding_model = load_embedding_model()
        print("Interactive RAG mode — type a question, or 'quit' to exit.")
        while True:
            user_question = input("> ")
            if user_question.strip().lower() == "quit":
                break
            run_rag_query(user_question, index_dir, embedding_model)
    except (FileNotFoundError, ValueError) as known_failure:
        print(f"Error: {known_failure}")
        sys.exit(1)


if __name__ == "__main__":
    main()

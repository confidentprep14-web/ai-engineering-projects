"""Embedding model loading and chunk embedding for semantic codebase search."""

import numpy as np
from sentence_transformers import SentenceTransformer


def load_model(model_name: str) -> SentenceTransformer:
    """Load a sentence-transformers model by name.

    sentence-transformers caches downloads locally under
    ~/.cache/huggingface/hub automatically — no extra caching logic needed
    here.
    """
    print(f"Loading model: {model_name}")
    return SentenceTransformer(model_name)


def embed_functions(chunks: list[dict], model) -> tuple[list, "np.ndarray | None"]:
    """Embed each chunk's function_name + text and return (chunks, embeddings).

    embeddings is a float32 numpy array of shape (N, D). If chunks is empty,
    returns ([], None) rather than calling the model on an empty batch.
    """
    if not chunks:
        return [], None

    texts = [f"{chunk['function_name']}: {chunk['text']}" for chunk in chunks]
    embeddings = model.encode(texts, show_progress_bar=True)
    embeddings = np.asarray(embeddings, dtype=np.float32)

    return chunks, embeddings

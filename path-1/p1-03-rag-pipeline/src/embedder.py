import os

import numpy as np
from sentence_transformers import SentenceTransformer


def _is_model_cached(model_name: str) -> bool:
    cache_root = os.environ.get(
        "SENTENCE_TRANSFORMERS_HOME",
        os.path.join(os.path.expanduser("~"), ".cache", "torch", "sentence_transformers"),
    )
    hf_cache_root = os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub")
    cached_dir_name = f"models--{model_name.replace('/', '--')}"
    return os.path.isdir(os.path.join(cache_root, model_name)) or os.path.isdir(
        os.path.join(hf_cache_root, cached_dir_name)
    )


def load_embedding_model() -> SentenceTransformer:
    model_name = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    if not _is_model_cached(model_name):
        print(f"Loading embedding model: {model_name}...")
    return SentenceTransformer(model_name)


def embed_texts(texts: list[str], model: SentenceTransformer) -> np.ndarray:
    embedding_matrix = model.encode(texts, batch_size=32, convert_to_numpy=True)
    return embedding_matrix.astype(np.float32)


def embed_query(query: str, model: SentenceTransformer) -> np.ndarray:
    return embed_texts([query], model)

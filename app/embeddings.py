import hashlib
import re

import numpy as np

from . import config

_local_model = None


def _normalize(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n else v


def _hash_embed(text: str, dim: int) -> list[float]:
    """Deterministic bag-of-words hashing embedding.

    Not semantic, but texts sharing words get similar vectors. Good enough for
    offline development and tests; use EMBEDDING_PROVIDER=local for real quality.
    """
    vec = np.zeros(dim, dtype=np.float32)
    for tok in re.findall(r"\w+", text.lower()):
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0 if (h >> 64) & 1 else -1.0
    return _normalize(vec).tolist()


def _local_embed(texts: list[str]) -> list[list[float]]:
    global _local_model
    if _local_model is None:
        from sentence_transformers import SentenceTransformer

        _local_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _local_model.encode(texts, normalize_embeddings=True).tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    if config.EMBEDDING_PROVIDER == "local":
        return _local_embed(texts)
    return [_hash_embed(t, config.EMBEDDING_DIM) for t in texts]


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]

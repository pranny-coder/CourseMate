import logging
import time

import numpy as np
from pymongo.database import Database

from . import config
from .embeddings import embed_query

log = logging.getLogger("coursemate.rag")

SYSTEM_PROMPT = (
    "You are a course assistant. Answer ONLY using the numbered context passages. "
    "Cite passages like [1] or [2]. If the answer is not in the context, say you "
    "don't know. Be concise."
)


def _vector_search(db: Database, qv: list[float], course_id, k: int) -> list[dict]:
    stage = {
        "index": config.VECTOR_INDEX_NAME,
        "path": "embedding",
        "queryVector": qv,
        "numCandidates": max(100, k * 20),
        "limit": k,
    }
    if course_id is not None:
        stage["filter"] = {"course_id": course_id}
    pipeline = [
        {"$vectorSearch": stage},
        {
            "$project": {
                "text": 1,
                "doc_id": 1,
                "idx": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]
    return list(db.chunks.aggregate(pipeline))


def _brute_force(db: Database, qv: list[float], course_id, k: int) -> list[dict]:
    """Fallback for local mongod / tests where $vectorSearch is unavailable."""
    q = np.asarray(qv, dtype=np.float32)
    flt = {"course_id": course_id} if course_id is not None else {}
    scored = []
    for c in db.chunks.find(flt, {"text": 1, "doc_id": 1, "idx": 1, "embedding": 1}):
        v = np.asarray(c["embedding"], dtype=np.float32)
        denom = np.linalg.norm(q) * np.linalg.norm(v)
        score = float(q @ v / denom) if denom else 0.0
        scored.append({**{x: c[x] for x in ("_id", "text", "doc_id", "idx")}, "score": score})
    scored.sort(key=lambda d: d["score"], reverse=True)
    return scored[:k]


def retrieve(db: Database, question: str, course_id=None, k: int = 5) -> tuple[list[dict], str]:
    qv = embed_query(question)
    try:
        return _vector_search(db, qv, course_id, k), "atlas_vector_search"
    except Exception as exc:  # OperationFailure on non-Atlas, NotImplementedError in mongomock
        log.info("Vector search unavailable (%s); using brute-force cosine", type(exc).__name__)
        return _brute_force(db, qv, course_id, k), "brute_force_cosine"


def generate_answer(question: str, hits: list[dict]) -> tuple[str, str]:
    """Returns (answer, mode). Falls back to extractive output with no API key."""
    if not hits:
        return "No relevant material found.", "none"

    context = "\n\n".join(f"[{i}] {h['text']}" for i, h in enumerate(hits, 1))
    if not config.ANTHROPIC_API_KEY:
        return "LLM not configured. Top matching passages:\n\n" + context, "extractive"

    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=config.LLM_MODEL,
        max_tokens=600,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}],
    )
    return msg.content[0].text, "llm"


def timed(fn, *args, **kwargs):
    t0 = time.perf_counter()
    out = fn(*args, **kwargs)
    return out, (time.perf_counter() - t0) * 1000

"""Business logic shared by the API, seed script and tests."""
from datetime import datetime, timezone

from bson import ObjectId
from pymongo.database import Database

from . import config
from .chunking import chunk_text
from .embeddings import embed_texts


def now() -> datetime:
    return datetime.now(timezone.utc)


def ingest_document(
    db: Database,
    course_id: ObjectId,
    title: str,
    text: str,
    source: str = "upload",
    tags: list[str] | None = None,
) -> dict:
    """Store a document, chunk it, embed the chunks, and store them.

    Schema decision: document metadata is small and read together, so it lives in
    `documents`. Chunks (many, each with a 384-float vector) are referenced via
    doc_id instead of embedded, which keeps the document under the 16 MB limit and
    lets the vector index cover `chunks` on its own.
    """
    pieces = chunk_text(text, config.CHUNK_WORDS, config.CHUNK_OVERLAP)
    vectors = embed_texts(pieces)

    doc = {
        "course_id": course_id,
        "title": title,
        "source": source,
        "tags": tags or [],
        "chunk_count": len(pieces),
        "created_at": now(),
    }
    doc_id = db.documents.insert_one(doc).inserted_id

    if pieces:
        db.chunks.insert_many(
            [
                {
                    "doc_id": doc_id,
                    "course_id": course_id,
                    "idx": i,
                    "text": p,
                    "embedding": v,
                    "created_at": doc["created_at"],
                }
                for i, (p, v) in enumerate(zip(pieces, vectors))
            ]
        )
    doc["_id"] = doc_id
    return doc


def delete_document(db: Database, doc_id: ObjectId) -> bool:
    res = db.documents.delete_one({"_id": doc_id})
    if res.deleted_count:
        db.chunks.delete_many({"doc_id": doc_id})
        return True
    return False

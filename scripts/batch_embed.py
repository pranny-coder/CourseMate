"""Embed any chunks missing a vector, in parallel batches.

Useful after switching EMBEDDING_PROVIDER or importing raw chunks.
Usage: python -m scripts.batch_embed [--workers 4] [--batch 64]

pymongo's MongoClient is thread-safe, and embedding/network calls release the GIL,
so a thread pool gives real speedup here.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor

from pymongo import UpdateOne

from app.db import get_db
from app.embeddings import embed_texts


def process(batch: list[dict]) -> int:
    db = get_db()
    vectors = embed_texts([c["text"] for c in batch])
    db.chunks.bulk_write(
        [UpdateOne({"_id": c["_id"]}, {"$set": {"embedding": v}}) for c, v in zip(batch, vectors)]
    )
    return len(batch)


def main(workers: int, batch_size: int) -> None:
    db = get_db()
    pending = list(db.chunks.find({"embedding": {"$exists": False}}, {"text": 1}))
    batches = [pending[i : i + batch_size] for i in range(0, len(pending), batch_size)]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        done = sum(pool.map(process, batches))
    print(f"Embedded {done} chunks in {len(batches)} batches with {workers} workers.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--batch", type=int, default=64)
    a = ap.parse_args()
    main(a.workers, a.batch)

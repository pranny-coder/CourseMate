"""Create regular indexes and (on Atlas) the vector search index.

Usage: python -m scripts.create_indexes
"""
from app.db import get_db
from app.indexes import ensure_indexes, ensure_vector_index

if __name__ == "__main__":
    db = get_db()
    ensure_indexes(db)
    print("Regular indexes ensured.")
    try:
        print("Vector index:", ensure_vector_index(db))
    except Exception as exc:
        print(f"Skipped vector index ({type(exc).__name__}: {exc}). "
              "Expected on local mongod; /ask will use brute-force cosine.")

"""Load sample courses and documents.  Usage: python -m scripts.seed"""
from pathlib import Path

from app import services
from app.db import get_db
from app.indexes import ensure_indexes

SAMPLES = Path(__file__).resolve().parent.parent / "data" / "sample_docs"

if __name__ == "__main__":
    db = get_db()
    ensure_indexes(db)

    course = db.courses.find_one({"code": "CS F212"})
    if not course:
        res = db.courses.insert_one(
            {"code": "CS F212", "name": "Database Systems", "description": "Sample course",
             "tags": ["dbms"], "created_at": services.now()}
        )
        course = {"_id": res.inserted_id}

    for path in sorted(SAMPLES.glob("*.txt")):
        title = path.stem.replace("_", " ").title()
        if db.documents.find_one({"title": title, "course_id": course["_id"]}):
            print("skip", title)
            continue
        d = services.ingest_document(db, course["_id"], title, path.read_text(), "seed", ["dbms"])
        print(f"ingested {title}: {d['chunk_count']} chunks")
    print("course_id:", course["_id"])

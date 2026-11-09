"""Measure the effect of the compound index with explain('executionStats').

Usage: python -m scripts.benchmark_indexes [--n 200000]
Uses a throwaway collection (bench_documents), so your real data is untouched.
"""
import argparse
import random
from datetime import datetime, timedelta, timezone

import pymongo
from bson import ObjectId

from app.db import get_db


def run(coll, course_id):
    cur = coll.find({"course_id": course_id}).sort("created_at", -1).limit(20)
    stats = cur.explain()["executionStats"]
    return stats["totalDocsExamined"], stats["totalKeysExamined"], stats["executionTimeMillis"]


def main(n: int) -> None:
    db = get_db()
    coll = db.bench_documents
    coll.drop()

    courses = [ObjectId() for _ in range(100)]
    base = datetime.now(timezone.utc)
    coll.insert_many(
        (
            {"course_id": random.choice(courses),
             "title": f"doc {i}",
             "created_at": base - timedelta(seconds=random.randint(0, 10_000_000))}
            for i in range(n)
        ),
        ordered=False,
    )
    target = courses[0]

    before = run(coll, target)
    coll.create_index([("course_id", 1), ("created_at", -1)], name="course_created")
    after = run(coll, target)

    print(f"\nQuery: find({{course_id}}).sort(created_at desc).limit(20) on {n:,} docs\n")
    print("| Metric | No index | Compound index |")
    print("|---|---|---|")
    print(f"| Docs examined | {before[0]:,} | {after[0]:,} |")
    print(f"| Keys examined | {before[1]:,} | {after[1]:,} |")
    print(f"| Execution time (ms) | {before[2]} | {after[2]} |")
    coll.drop()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200_000)
    main(ap.parse_args().n)

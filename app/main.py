from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from . import config, rag, services
from .db import get_db
from .schemas import (AskIn, CourseIn, CourseUpdate, DocumentIn, DocumentUpdate,
                      UserIn)
from .static_html import HTML_CONTENT
from .utils import oid, ser

app = FastAPI(title="CourseMate", description="Course Q&A on MongoDB Atlas (RAG)")


# --- Global exception handler: always return JSON, never plain-text 500 ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {str(exc)}"},
    )


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
@app.get("/api", response_class=HTMLResponse, include_in_schema=False)
@app.get("/api/", response_class=HTMLResponse, include_in_schema=False)
@app.get("/api/index", response_class=HTMLResponse, include_in_schema=False)
@app.get("/api/index.py", response_class=HTMLResponse, include_in_schema=False)
def index():
    return HTMLResponse(content=HTML_CONTENT)


# NOTE: endpoints are plain `def` on purpose. pymongo is blocking, so FastAPI runs
# them in its threadpool and concurrent requests don't stall the event loop.


@app.get("/health")
def health():
    """DB connectivity probe — always returns JSON with diagnostics."""
    import os
    import ssl
    # Show masked URI so we can confirm env var is loaded
    uri = os.environ.get("MONGODB_URI", config.MONGODB_URI)
    if "@" in uri:
        masked = "mongodb+srv://***@" + uri.split("@", 1)[1]
    else:
        masked = uri

    try:
        from pymongo import MongoClient
        # Force TLS 1.2 to avoid OpenSSL 3.x / Atlas handshake issue on Vercel Lambda
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.maximum_version = ssl.TLSVersion.TLSv1_2
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        client = MongoClient(uri, serverSelectionTimeoutMS=8000, ssl_context=ctx)
        info = client.admin.command("hello")
        primary = info.get("primary") or ("standalone" if info.get("isWritablePrimary") else "unknown")
        return {"ok": True, "primary": primary, "hosts": info.get("hosts", []), "uri": masked}
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={"ok": False, "error": f"{type(exc).__name__}: {str(exc)}", "uri": masked},
        )


# ---------- Courses (CRUD) ----------
@app.post("/courses", status_code=201)
def create_course(body: CourseIn, db: Database = Depends(get_db)):
    doc = {**body.model_dump(), "created_at": services.now()}
    try:
        doc["_id"] = db.courses.insert_one(doc).inserted_id
    except DuplicateKeyError:
        raise HTTPException(409, f"Course code '{body.code}' already exists")
    return ser(doc)


@app.get("/courses")
def list_courses(db: Database = Depends(get_db)):
    return [ser(c) for c in db.courses.find().sort("code", 1)]


@app.get("/courses/{course_id}")
def get_course(course_id: str, db: Database = Depends(get_db)):
    c = db.courses.find_one({"_id": oid(course_id)})
    if not c:
        raise HTTPException(404, "Course not found")
    return ser(c)


@app.patch("/courses/{course_id}")
def update_course(course_id: str, body: CourseUpdate, db: Database = Depends(get_db)):
    changes = body.model_dump(exclude_none=True)
    if not changes:
        raise HTTPException(422, "Nothing to update")
    c = db.courses.find_one_and_update(
        {"_id": oid(course_id)}, {"$set": changes}, return_document=True
    )
    if not c:
        raise HTTPException(404, "Course not found")
    return ser(c)


@app.delete("/courses/{course_id}", status_code=204)
def delete_course(course_id: str, db: Database = Depends(get_db)):
    cid = oid(course_id)
    if not db.courses.delete_one({"_id": cid}).deleted_count:
        raise HTTPException(404, "Course not found")
    db.documents.delete_many({"course_id": cid})
    db.chunks.delete_many({"course_id": cid})


# ---------- Users ----------
@app.post("/users", status_code=201)
def create_user(body: UserIn, db: Database = Depends(get_db)):
    doc = {**body.model_dump(), "created_at": services.now()}
    try:
        doc["_id"] = db.users.insert_one(doc).inserted_id
    except DuplicateKeyError:
        raise HTTPException(409, "Email already registered")
    return ser(doc)


# ---------- Documents (CRUD + ingestion) ----------
@app.post("/documents", status_code=201)
def create_document(body: DocumentIn, db: Database = Depends(get_db)):
    cid = oid(body.course_id)
    if not db.courses.find_one({"_id": cid}, {"_id": 1}):
        raise HTTPException(404, "Course not found")
    doc = services.ingest_document(db, cid, body.title, body.text, body.source, body.tags)
    return ser(doc)


@app.get("/documents")
def list_documents(
    course_id: str | None = None,
    q: str | None = Query(None, description="Full-text search on title/tags"),
    limit: int = Query(20, ge=1, le=100),
    skip: int = Query(0, ge=0),
    db: Database = Depends(get_db),
):
    flt: dict = {}
    if course_id:
        flt["course_id"] = oid(course_id)
    if q:
        flt["$text"] = {"$search": q}
    # (course_id, created_at desc) index serves both the filter and the sort
    cur = db.documents.find(flt).sort("created_at", -1).skip(skip).limit(limit)
    return [ser(d) for d in cur]


@app.get("/documents/{doc_id}")
def get_document(doc_id: str, db: Database = Depends(get_db)):
    d = db.documents.find_one({"_id": oid(doc_id)})
    if not d:
        raise HTTPException(404, "Document not found")
    return ser(d)


@app.patch("/documents/{doc_id}")
def update_document(doc_id: str, body: DocumentUpdate, db: Database = Depends(get_db)):
    changes = body.model_dump(exclude_none=True)
    if not changes:
        raise HTTPException(422, "Nothing to update")
    d = db.documents.find_one_and_update(
        {"_id": oid(doc_id)}, {"$set": changes}, return_document=True
    )
    if not d:
        raise HTTPException(404, "Document not found")
    return ser(d)


@app.delete("/documents/{doc_id}", status_code=204)
def delete_document(doc_id: str, db: Database = Depends(get_db)):
    if not services.delete_document(db, oid(doc_id)):
        raise HTTPException(404, "Document not found")


# ---------- RAG ----------
@app.post("/ask")
def ask(body: AskIn, db: Database = Depends(get_db)):
    cid = oid(body.course_id) if body.course_id else None
    uid = oid(body.user_id) if body.user_id else None

    try:
        t0 = datetime.now(timezone.utc)
        (hits, retrieval_mode) = rag.retrieve(db, body.question, cid, body.k)
        answer, answer_mode = rag.generate_answer(body.question, hits)
        latency_ms = (datetime.now(timezone.utc) - t0).total_seconds() * 1000
    except Exception as exc:
        raise HTTPException(503, f"Retrieval failed: {type(exc).__name__}: {str(exc)}")

    titles = {
        d["_id"]: d["title"]
        for d in db.documents.find({"_id": {"$in": list({h["doc_id"] for h in hits})}}, {"title": 1})
    }
    sources = [
        {
            "n": i,
            "doc_id": str(h["doc_id"]),
            "title": titles.get(h["doc_id"], "?"),
            "chunk_idx": h["idx"],
            "score": round(h["score"], 4),
            "snippet": h["text"][:200],
        }
        for i, h in enumerate(hits, 1)
    ]

    db.query_logs.insert_one(
        {
            "question": body.question,
            "course_id": cid,
            "user_id": uid,
            "top_score": hits[0]["score"] if hits else None,
            "n_hits": len(hits),
            "source_doc_ids": list({h["doc_id"] for h in hits}),
            "retrieval_mode": retrieval_mode,
            "answer_mode": answer_mode,
            "latency_ms": latency_ms,
            "created_at": services.now(),
        }
    )
    return {
        "answer": answer,
        "sources": sources,
        "retrieval_mode": retrieval_mode,
        "answer_mode": answer_mode,
        "latency_ms": round(latency_ms, 1),
    }


# ---------- Analytics (aggregation pipelines) ----------
@app.get("/analytics/queries-per-day")
def queries_per_day(db: Database = Depends(get_db)):
    pipeline = [
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
            "queries": {"$sum": 1},
        }},
        {"$sort": {"_id": 1}},
        {"$project": {"_id": 0, "day": "$_id", "queries": 1}},
    ]
    return list(db.query_logs.aggregate(pipeline))


@app.get("/analytics/course-stats")
def course_stats(db: Database = Depends(get_db)):
    pipeline = [
        {"$match": {"course_id": {"$ne": None}}},
        {"$group": {
            "_id": "$course_id",
            "queries": {"$sum": 1},
            "avg_top_score": {"$avg": "$top_score"},
            "avg_latency_ms": {"$avg": "$latency_ms"},
        }},
        {"$lookup": {"from": "courses", "localField": "_id", "foreignField": "_id", "as": "course"}},
        {"$unwind": "$course"},
        {"$project": {
            "_id": 0,
            "course_code": "$course.code",
            "queries": 1,
            "avg_top_score": 1,
            "avg_latency_ms": 1,
        }},
        {"$sort": {"queries": -1}},
    ]
    rows = list(db.query_logs.aggregate(pipeline))
    for r in rows:
        r["avg_top_score"] = round(r["avg_top_score"] or 0, 4)
        r["avg_latency_ms"] = round(r["avg_latency_ms"] or 0, 1)
    return rows


@app.get("/analytics/top-documents")
def top_documents(limit: int = Query(5, ge=1, le=50), db: Database = Depends(get_db)):
    """Which documents get cited most often in answers."""
    pipeline = [
        {"$unwind": "$source_doc_ids"},
        {"$group": {"_id": "$source_doc_ids", "times_retrieved": {"$sum": 1}}},
        {"$sort": {"times_retrieved": -1}},
        {"$limit": limit},
        {"$lookup": {"from": "documents", "localField": "_id", "foreignField": "_id", "as": "doc"}},
        {"$unwind": "$doc"},
        {"$project": {"_id": 0, "title": "$doc.title", "times_retrieved": 1}},
    ]
    return list(db.query_logs.aggregate(pipeline))

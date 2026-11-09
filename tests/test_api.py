import mongomock
import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr("app.config.ANTHROPIC_API_KEY", "")
    db = mongomock.MongoClient().coursemate
    db.courses.create_index("code", unique=True)
    db.users.create_index("email", unique=True)
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app), db
    app.dependency_overrides.clear()


DOC_TEXT = (
    "A B-Tree index speeds up equality lookups and range scans on a column. "
    "Composite indexes follow the leftmost prefix rule. " * 10
)


def make_course(c, code="CS F212"):
    return c.post("/courses", json={"code": code, "name": "Database Systems"})


def test_index_page(client):
    c, _ = client
    r = c.get("/")
    assert r.status_code == 200
    assert "CourseMate" in r.text


def test_course_crud_and_duplicate(client):
    c, _ = client
    r = make_course(c)
    assert r.status_code == 201
    cid = r.json()["id"]

    assert make_course(c).status_code == 409
    assert c.get(f"/courses/{cid}").json()["code"] == "CS F212"
    assert c.patch(f"/courses/{cid}", json={"name": "DBMS"}).json()["name"] == "DBMS"
    assert c.delete(f"/courses/{cid}").status_code == 204
    assert c.get(f"/courses/{cid}").status_code == 404


def test_invalid_id_is_422(client):
    c, _ = client
    assert c.get("/courses/not-an-id").status_code == 422


def test_user_unique_email(client):
    c, _ = client
    body = {"email": "a@b.com", "name": "A"}
    assert c.post("/users", json=body).status_code == 201
    assert c.post("/users", json=body).status_code == 409


def test_document_ingest_creates_chunks_and_delete_cascades(client):
    c, db = client
    cid = make_course(c).json()["id"]
    r = c.post("/documents", json={"course_id": cid, "title": "Indexes", "text": DOC_TEXT})
    assert r.status_code == 201
    doc = r.json()
    assert doc["chunk_count"] >= 1
    assert db.chunks.count_documents({}) == doc["chunk_count"]

    assert c.delete(f"/documents/{doc['id']}").status_code == 204
    assert db.chunks.count_documents({}) == 0


def test_document_for_missing_course_404(client):
    c, _ = client
    r = c.post("/documents", json={"course_id": "0" * 24, "title": "x", "text": "y"})
    assert r.status_code == 404


def test_ask_returns_sources_and_logs_query(client):
    c, db = client
    cid = make_course(c).json()["id"]
    c.post("/documents", json={"course_id": cid, "title": "Indexes", "text": DOC_TEXT})
    c.post("/documents", json={"course_id": cid, "title": "Sports",
                               "text": "Kho kho is a tag sport played in India. " * 20})

    r = c.post("/ask", json={"question": "how does a b-tree index help lookups?", "course_id": cid})
    assert r.status_code == 200
    body = r.json()
    assert body["sources"], "expected at least one source"
    assert body["sources"][0]["title"] == "Indexes"
    assert db.query_logs.count_documents({}) == 1


def test_analytics_after_queries(client):
    c, _ = client
    cid = make_course(c).json()["id"]
    c.post("/documents", json={"course_id": cid, "title": "Indexes", "text": DOC_TEXT})
    for _ in range(2):
        c.post("/ask", json={"question": "what is a composite index?", "course_id": cid})

    per_day = c.get("/analytics/queries-per-day").json()
    assert per_day[0]["queries"] == 2
    stats = c.get("/analytics/course-stats").json()
    assert stats[0]["course_code"] == "CS F212" and stats[0]["queries"] == 2
    top = c.get("/analytics/top-documents").json()
    assert top[0]["title"] == "Indexes"

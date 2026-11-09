"""All index definitions in one place so they can be documented and benchmarked."""
import pymongo
from pymongo.database import Database
from pymongo.operations import SearchIndexModel

from . import config


def ensure_indexes(db: Database) -> None:
    db.courses.create_index("code", unique=True, name="uniq_course_code")
    db.users.create_index("email", unique=True, name="uniq_user_email")

    # Serves: list a course's documents newest-first (equality + sort, no in-memory sort)
    db.documents.create_index(
        [("course_id", pymongo.ASCENDING), ("created_at", pymongo.DESCENDING)],
        name="course_created",
    )
    db.documents.create_index(
        [("title", "text"), ("tags", "text")], name="doc_text_search"
    )

    db.chunks.create_index(
        [("doc_id", pymongo.ASCENDING), ("idx", pymongo.ASCENDING)],
        unique=True,
        name="uniq_doc_chunk",
    )
    db.chunks.create_index("course_id", name="chunk_course")

    db.query_logs.create_index("created_at", name="log_created")
    db.query_logs.create_index(
        [("course_id", pymongo.ASCENDING), ("created_at", pymongo.DESCENDING)],
        name="log_course_created",
    )


def ensure_vector_index(db: Database) -> str:
    """Create the Atlas Vector Search index (Atlas only; not available on plain mongod)."""
    existing = {i["name"] for i in db.chunks.list_search_indexes()}
    if config.VECTOR_INDEX_NAME in existing:
        return "exists"
    model = SearchIndexModel(
        name=config.VECTOR_INDEX_NAME,
        type="vectorSearch",
        definition={
            "fields": [
                {
                    "type": "vector",
                    "path": "embedding",
                    "numDimensions": config.EMBEDDING_DIM,
                    "similarity": "cosine",
                },
                {"type": "filter", "path": "course_id"},
            ]
        },
    )
    db.chunks.create_search_index(model)
    return "created"

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException


def oid(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=422, detail=f"Invalid id: {value}")


def ser(doc: dict | None) -> dict | None:
    """Make a Mongo document JSON-safe: _id -> id, ObjectId -> str."""
    if doc is None:
        return None
    out = {}
    for k, v in doc.items():
        key = "id" if k == "_id" else k
        out[key] = str(v) if isinstance(v, ObjectId) else v
    return out

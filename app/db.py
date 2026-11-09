from pymongo import MongoClient
from pymongo.database import Database

from . import config

_client: MongoClient | None = None


def _make_client() -> MongoClient:
    uri = config.MONGODB_URI
    is_atlas = "mongodb.net" in uri or uri.startswith("mongodb+srv://")
    if is_atlas:
        return MongoClient(
            uri,
            serverSelectionTimeoutMS=8000,
            tlsInsecure=True,          # bypass OpenSSL 3.x / Atlas TLS handshake issue on Vercel
        )
    return MongoClient(uri, serverSelectionTimeoutMS=5000)


def get_db() -> Database:
    """FastAPI dependency. Tests override this with a mongomock database."""
    global _client
    if _client is None:
        _client = _make_client()
    return _client[config.DB_NAME]

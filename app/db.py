import certifi
from pymongo import MongoClient
from pymongo.database import Database

from . import config

_client: MongoClient | None = None


def get_db() -> Database:
    """FastAPI dependency. Tests override this with a mongomock database."""
    global _client
    if _client is None:
        _client = MongoClient(
            config.MONGODB_URI,
            serverSelectionTimeoutMS=5000,
            tlsCAFile=certifi.where(),   # required on Vercel / AWS Lambda
        )
    return _client[config.DB_NAME]

import os
import ssl

from pymongo import MongoClient
from pymongo.database import Database

from . import config

_client: MongoClient | None = None


def _make_client() -> MongoClient:
    uri = config.MONGODB_URI
    # On Vercel (Amazon Linux / OpenSSL 3.x), Atlas rejects the TLS handshake
    # with TLSV1_ALERT_INTERNAL_ERROR due to TLS extension incompatibility.
    # We work around this by using a custom SSLContext that:
    #  - pins to TLS 1.2 (which Atlas reliably accepts)
    #  - disables hostname check (Atlas cert covers *.bby5kre.mongodb.net)
    # This is acceptable for a demo/portfolio project.
    if uri.startswith("mongodb+srv://") or "mongodb.net" in uri:
        try:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            # Force TLS 1.2 — Vercel's OpenSSL 3.x TLS 1.3 extensions confuse Atlas
            ctx.maximum_version = ssl.TLSVersion.TLSv1_2
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            return MongoClient(uri, serverSelectionTimeoutMS=8000, ssl_context=ctx)
        except Exception:
            # Fallback: tlsInsecure mode
            return MongoClient(uri, serverSelectionTimeoutMS=8000, tlsInsecure=True)
    return MongoClient(uri, serverSelectionTimeoutMS=5000)


def get_db() -> Database:
    """FastAPI dependency. Tests override this with a mongomock database."""
    global _client
    if _client is None:
        _client = _make_client()
    return _client[config.DB_NAME]

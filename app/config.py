import os

from dotenv import load_dotenv

load_dotenv(override=True)

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/?replicaSet=rs0")
DB_NAME = os.getenv("DB_NAME", "coursemate")

EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "hash")  # hash | local
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "384"))

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-5-5")

CHUNK_WORDS = int(os.getenv("CHUNK_WORDS", "120"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "20"))
TOP_K = int(os.getenv("TOP_K", "5"))

VECTOR_INDEX_NAME = "chunk_vector_index"

# CourseMate

RAG-based course Q&A backend on **MongoDB Atlas** (Python, FastAPI). Upload course material, search it, and ask questions answered from the documents with cited sources.

## Architecture

```
Client -> FastAPI (REST) -> MongoDB (Atlas / 3-node replica set)
                |-- /documents : chunk -> embed -> store in `chunks`
                |-- /ask       : embed query -> $vectorSearch top-k -> LLM -> answer + sources
                `-- /analytics : aggregation pipelines over `query_logs`
```

## Schema

| Collection | Key fields | Design note |
|---|---|---|
| `courses` | code (unique), name, tags[] | tags embedded: small, read with the course |
| `documents` | course_id, title, tags[], chunk_count, created_at | metadata only |
| `chunks` | doc_id, course_id, idx, text, embedding[384] | **referenced**, not embedded: many per doc, large vectors, 16 MB doc limit, separate vector index |
| `users` | email (unique), name | |
| `query_logs` | question, course_id, top_score, source_doc_ids[], latency_ms, created_at | feeds analytics |

## Indexes (`app/indexes.py`)

| Index | Why |
|---|---|
| `courses.code` unique, `users.email` unique | integrity (409 on duplicates) |
| `documents (course_id, created_at desc)` | equality + sort served from the index |
| `documents text(title, tags)` | `GET /documents?q=` |
| `chunks (doc_id, idx)` unique, `chunks course_id` | cascade delete, filtered retrieval |
| `query_logs created_at`, `(course_id, created_at)` | analytics |
| `chunks.embedding` **Atlas Vector Search** (cosine, 384 dims, filter on course_id) | semantic retrieval |

## Run on Atlas (free M0)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # set MONGODB_URI to your Atlas string
python -m scripts.create_indexes # regular indexes + vector search index
python -m scripts.seed           # sample course + 3 documents
uvicorn app.main:app --reload    # http://localhost:8000/docs
```

Atlas builds the vector index asynchronously; wait until it shows **Active** before expecting `retrieval_mode: atlas_vector_search`.

Optional real embeddings: `pip install -r requirements-ml.txt` and set `EMBEDDING_PROVIDER=local`. Optional LLM answers: set `ANTHROPIC_API_KEY`. Without it `/ask` returns the top passages (extractive mode).

> If you change `EMBEDDING_PROVIDER`, existing vectors are incompatible. Drop `chunks` and re-run `seed`.

## Run locally with Docker (replica set)

```bash
docker compose up --build
curl localhost:8000/health
docker compose exec api python -m scripts.seed
```

Local `mongod` has no `$vectorSearch`, so `/ask` falls back to brute-force cosine (the response says which mode ran).

### Replication / failover demo

```bash
curl localhost:8000/health        # note "primary"
docker compose stop mongo1        # kill the primary
sleep 10
curl localhost:8000/health        # new primary elected
curl localhost:8000/courses       # reads/writes still work
docker compose start mongo1       # rejoins as secondary
```

## Try it

```bash
CID=$(curl -s -XPOST localhost:8000/courses -H 'content-type: application/json' \
  -d '{"code":"CS F212","name":"Database Systems"}' | python -c "import sys,json;print(json.load(sys.stdin)['id'])")
curl -XPOST localhost:8000/ask -H 'content-type: application/json' \
  -d "{\"question\":\"Why use a composite index?\",\"course_id\":\"$CID\"}"
curl localhost:8000/analytics/course-stats
```

## Benchmark indexes

```bash
python -m scripts.benchmark_indexes --n 200000
```
Paste your output here:

| Metric | No index | Compound index |
|---|---|---|
| Docs examined | _run it_ | _run it_ |
| Execution time (ms) | _run it_ | _run it_ |

## Concurrency

Endpoints are sync `def` so FastAPI runs them in a threadpool (pymongo is blocking). `scripts/batch_embed.py` re-embeds chunks with a `ThreadPoolExecutor`.

## Tests and CI

```bash
pip install -r requirements-dev.txt && pytest -q
```
Tests use `mongomock` (no database needed). GitHub Actions runs them and builds the Docker image on every push.

## Sharding (design only, not implemented)

M0 can't shard. If `chunks` outgrew one replica set, the shard key would be `{course_id: 1, _id: 1}`: queries filter by course (targeted, not scatter-gather), and adding `_id` keeps cardinality high so a popular course can still split across chunks. A key like `created_at` alone would be monotonically increasing and create a hot shard.

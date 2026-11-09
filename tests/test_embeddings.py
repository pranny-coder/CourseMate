import numpy as np

from app import config
from app.embeddings import embed_query, embed_texts


def test_dimension_and_unit_norm():
    v = embed_query("b-tree index lookup")
    assert len(v) == config.EMBEDDING_DIM
    assert abs(np.linalg.norm(v) - 1.0) < 1e-4


def test_deterministic():
    assert embed_query("replica set election") == embed_query("replica set election")


def test_related_text_scores_higher():
    q = np.array(embed_query("how does a b-tree index speed up lookups"))
    related, unrelated = embed_texts([
        "a b-tree index speeds up lookups by keeping keys sorted",
        "kho kho is a tag sport played in india",
    ])
    assert q @ np.array(related) > q @ np.array(unrelated)

"""Integration tests against a REAL Postgres + pgvector instance, not a
mock. Skipped automatically if it isn't reachable, so the main suite
still runs offline for anyone without Docker -- start it with:
    docker run -d --name asr-postgres -p 5432:5432 \
        -e POSTGRES_PASSWORD=testpassword123 -e POSTGRES_DB=agentic_ref \
        ankane/pgvector:latest

Embeddings here are small, hand-picked vectors, not real model
embeddings -- the point is proving pgvector's actual nearest-neighbor
search mechanism works correctly against real data, which doesn't
require real embedding quality to verify.
"""
import pytest

from document_intelligence.retrieval import PgVectorStore

CONNINFO = "host=localhost port=5432 dbname=agentic_ref user=postgres password=testpassword123"


def _postgres_available() -> bool:
    try:
        import psycopg

        conn = psycopg.connect(CONNINFO, connect_timeout=2)
        conn.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _postgres_available(), reason="Postgres is not running on localhost:5432")


@pytest.fixture
def store():
    s = PgVectorStore(CONNINFO, dimensions=4)
    s.clear()
    yield s
    s.clear()
    s.close()


def test_search_returns_the_nearest_chunk_first(store):
    store.add_chunk("apple", [1.0, 0.0, 0.0, 0.0])
    store.add_chunk("banana", [0.0, 1.0, 0.0, 0.0])
    store.add_chunk("cherry", [0.0, 0.0, 1.0, 0.0])

    results = store.search([0.9, 0.1, 0.0, 0.0], top_k=3)

    assert results[0][0] == "apple"  # nearest by real L2 distance
    assert results[0][1] < results[1][1] < results[2][1]  # distances genuinely ascending


def test_search_respects_top_k(store):
    store.add_chunk("apple", [1.0, 0.0, 0.0, 0.0])
    store.add_chunk("banana", [0.0, 1.0, 0.0, 0.0])
    store.add_chunk("cherry", [0.0, 0.0, 1.0, 0.0])

    results = store.search([1.0, 0.0, 0.0, 0.0], top_k=1)
    assert len(results) == 1
    assert results[0][0] == "apple"

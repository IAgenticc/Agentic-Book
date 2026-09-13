"""pgvector-backed retrieval (Chapter 8): a real vector database doing
real nearest-neighbor search over embedded chunks, the mechanism
Chapter 8's "Build it" section describes `vector_db.search` as standing
in for.
"""
from __future__ import annotations

import psycopg
from pgvector.psycopg import register_vector


class PgVectorStore:
    def __init__(self, conninfo: str, dimensions: int):
        self._conn = psycopg.connect(conninfo, autocommit=True)
        self._conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        register_vector(self._conn)
        self._conn.execute(
            f"CREATE TABLE IF NOT EXISTS chunks ("
            f"id SERIAL PRIMARY KEY, text TEXT NOT NULL, embedding vector({dimensions}))"
        )

    def close(self) -> None:
        self._conn.close()

    def clear(self) -> None:
        """Testing convenience only."""
        self._conn.execute("TRUNCATE chunks")

    def add_chunk(self, text: str, embedding: list[float]) -> None:
        self._conn.execute("INSERT INTO chunks (text, embedding) VALUES (%s, %s)", (text, embedding))

    def search(self, query_embedding: list[float], top_k: int = 3) -> list[tuple[str, float]]:
        """Approximate nearest-neighbor search using pgvector's L2 distance
        operator (<->) -- the real mechanism, not a mock of it."""
        cur = self._conn.execute(
            "SELECT text, embedding <-> %s::vector AS distance FROM chunks ORDER BY distance LIMIT %s",
            (query_embedding, top_k),
        )
        return [(row[0], row[1]) for row in cur.fetchall()]

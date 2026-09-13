"""Neo4j-backed fact graph (Chapter 38) -- the production-scale sibling
of the in-process NetworkX example in the chapter's "Build it" section.
Same interface (add a relationship, ask what touches a changed entity),
a real graph database underneath instead of an in-memory structure, so
this actually survives the process and can be queried by more than one
service at once, exactly what the chapter argues NetworkX doesn't do.
"""
from __future__ import annotations

from neo4j import GraphDatabase


class Neo4jFactGraph:
    def __init__(self, uri: str, user: str, password: str):
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self) -> None:
        self._driver.close()

    def clear(self) -> None:
        """Testing convenience only -- a real deployment never wants this."""
        with self._driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")

    def add_relationship(self, subject: str, relationship: str, obj: str) -> None:
        with self._driver.session() as session:
            session.run(
                "MERGE (s:Entity {name: $subject}) "
                "MERGE (o:Entity {name: $object}) "
                "MERGE (s)-[r:RELATES {type: $relationship}]->(o)",
                subject=subject,
                object=obj,
                relationship=relationship,
            )

    def find_affected(self, changed_entity: str) -> list[tuple[str, str, str]]:
        """Same question Chapter 38's find_affected() answers: given that
        this entity changed, which edges touch it? Here, a real Cypher
        traversal instead of an in-memory graph walk."""
        with self._driver.session() as session:
            result = session.run(
                "MATCH (s:Entity)-[r:RELATES]->(o:Entity {name: $entity}) "
                "RETURN s.name AS subject, r.type AS relationship, o.name AS object",
                entity=changed_entity,
            )
            return [(record["subject"], record["relationship"], record["object"]) for record in result]

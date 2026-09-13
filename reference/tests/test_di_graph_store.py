"""Integration tests against a REAL Neo4j instance, not a mock. Skipped
automatically if Neo4j isn't reachable, so the main suite still runs
offline for anyone without Docker -- start it with:
    docker run -d --name asr-neo4j -p 7474:7474 -p 7687:7687 \
        -e NEO4J_AUTH=neo4j/testpassword123 neo4j:5-community
"""
import pytest

from document_intelligence.graph_store import Neo4jFactGraph

NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "testpassword123")


def _neo4j_available() -> bool:
    try:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
        driver.verify_connectivity()
        driver.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _neo4j_available(), reason="Neo4j is not running on localhost:7687")


@pytest.fixture
def graph():
    g = Neo4jFactGraph(NEO4J_URI, *NEO4J_AUTH)
    g.clear()
    yield g
    g.clear()
    g.close()


def test_find_affected_returns_every_edge_touching_the_changed_entity(graph):
    """The exact same scenario and assertion as Chapter 38's NetworkX
    example -- same interface, a real graph database underneath instead
    of an in-memory structure."""
    graph.add_relationship("Acme Corp", "primary_contact", "Jane Smith")
    graph.add_relationship("Acme Logistics", "primary_contact", "Jane Smith")
    graph.add_relationship("Acme Logistics", "subsidiary_of", "Acme Corp")

    affected = graph.find_affected("Jane Smith")

    assert len(affected) == 2
    subjects = {a[0] for a in affected}
    assert subjects == {"Acme Corp", "Acme Logistics"}
    assert all(a[1] == "primary_contact" for a in affected)


def test_find_affected_returns_nothing_for_an_unconnected_entity(graph):
    graph.add_relationship("Acme Corp", "primary_contact", "Jane Smith")
    assert graph.find_affected("Someone Else Entirely") == []


def test_find_affected_does_not_return_unrelated_edges(graph):
    graph.add_relationship("Acme Corp", "primary_contact", "Jane Smith")
    graph.add_relationship("Acme Logistics", "subsidiary_of", "Acme Corp")
    # subsidiary_of targets "Acme Corp", not "Jane Smith" -- shouldn't show up here
    affected = graph.find_affected("Jane Smith")
    assert len(affected) == 1
    assert affected[0] == ("Acme Corp", "primary_contact", "Jane Smith")

"""guard_cypher: the first of the MCP agent's read-only layers."""
import pytest

from app.retrieval.mcp_agent import guard_cypher


def test_adds_limit_when_missing():
    assert guard_cypher("MATCH (p:Person) RETURN p.email", 10) == "MATCH (p:Person) RETURN p.email LIMIT 10"


def test_caps_large_limit_and_keeps_small_one():
    assert guard_cypher("MATCH (p:Person) RETURN p.email LIMIT 500;", 10).endswith("LIMIT 10")
    assert guard_cypher("MATCH (p:Person) RETURN p.email LIMIT 3", 10).endswith("LIMIT 3")


def test_keywords_inside_strings_are_fine():
    q = "MATCH (e:Email) WHERE e.subject CONTAINS 'merge; delete' RETURN e.subject"
    assert guard_cypher(q, 5).startswith(q)


def test_fulltext_procedure_and_subquery_allowed():
    guard_cypher("CALL db.index.fulltext.queryNodes('person_name_fuzzy', 'lay') YIELD node RETURN node.email", 5)
    guard_cypher("MATCH (p:Person) CALL { WITH p RETURN 1 AS x } RETURN p.email, x", 5)


@pytest.mark.parametrize("query", [
    "CREATE (n:X) RETURN n",
    "MATCH (n) DETACH DELETE n RETURN 1",
    "MATCH (p:Person) SET p.name = 'x' RETURN p",
    "MERGE (p:Person {email: 'a'}) RETURN p",
    "MATCH (n) RETURN n; MATCH (m) DELETE m",
    "CALL apoc.meta.schema() YIELD value RETURN value",
    "CALL dbms.listConfig() YIELD name RETURN name",
    "LOAD CSV FROM 'file:///x' AS r RETURN r",
    "SHOW USERS",
    "MATCH (p:Person) RETURN p.email // LIMIT 1",
    "MATCH (p:Person) RETURN p.email LIMIT $n",
    "MATCH (p:Person) WHERE p.email = 'unclosed RETURN p",
    "MATCH (p:Person)",
])
def test_rejects_unsafe_or_unbounded(query):
    with pytest.raises(ValueError):
        guard_cypher(query, 10)

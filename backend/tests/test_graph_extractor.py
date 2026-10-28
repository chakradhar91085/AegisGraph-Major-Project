import pytest
from app.retrieval.graph_extractor import graph_extractor, GraphVisualizationPayload
from app.retrieval.schemas import RetrievalResponse, ResolvedEntity, ResolutionStatus

def test_frequent_communication_extraction():
    # Setup mock response using the real schema fields returned by
    # strategies.get_frequent_communication (email / name / email_count).
    resolved = ResolvedEntity(
        type="employee",
        query_value="veronica",
        status=ResolutionStatus.FOUND,
        matches=[{"email": "veronica.espinoza@enron.com", "name": "Veronica Espinoza"}]
    )

    response = RetrievalResponse(
        query="Who does veronica communicate with?",
        intent="frequent_communication",
        resolved_entities=[resolved],
        results=[
            {"email": "russell.diamond@enron.com", "name": "Russell Diamond", "email_count": 139},
            {"email": "john.doe@enron.com", "name": "John Doe", "email_count": 50}
        ],
        result_count=2,
        strategy="frequent_communication"
    )

    payload = graph_extractor.extract(response)

    # Assert nodes
    assert len(payload.nodes) == 3
    node_ids = {n.id for n in payload.nodes}
    assert "veronica.espinoza@enron.com" in node_ids
    assert "russell.diamond@enron.com" in node_ids
    assert "john.doe@enron.com" in node_ids

    # Assert edges
    assert len(payload.edges) == 2
    for e in payload.edges:
        assert e.source == "veronica.espinoza@enron.com"
        assert e.type == "COMMUNICATES_FREQUENTLY_WITH"
        assert e.weight in [139, 50]

def test_frequent_communication_missing_email_does_not_collapse_nodes():
    # Regression test for the fallback-id bug: rows missing the expected
    # 'email' field must each get a distinct placeholder id, not all
    # collapse onto the same "unknown_email" node.
    resolved = ResolvedEntity(
        type="employee",
        query_value="veronica",
        status=ResolutionStatus.FOUND,
        matches=[{"email": "veronica.espinoza@enron.com", "name": "Veronica Espinoza"}]
    )
    response = RetrievalResponse(
        query="Who does veronica communicate with?",
        intent="frequent_communication",
        resolved_entities=[resolved],
        results=[
            {"name": "Person A", "email_count": 10},
            {"name": "Person B", "email_count": 5},
        ],
        result_count=2,
        strategy="frequent_communication"
    )

    payload = graph_extractor.extract(response)
    target_ids = {n.id for n in payload.nodes if n.id != "veronica.espinoza@enron.com"}
    assert len(target_ids) == 2

def test_person_connection_extraction():
    # Mock data matches the real fields returned by
    # strategies.get_person_connection (from_email / via_email_subject / to_email).
    resolved1 = ResolvedEntity(
        type="employee",
        query_value="john",
        status=ResolutionStatus.FOUND,
        matches=[{"email": "john@enron.com", "name": "John"}]
    )
    resolved2 = ResolvedEntity(
        type="employee",
        query_value="jane",
        status=ResolutionStatus.FOUND,
        matches=[{"email": "jane@enron.com", "name": "Jane"}]
    )

    response = RetrievalResponse(
        query="connection between john and jane",
        intent="person_connection",
        resolved_entities=[resolved1, resolved2],
        results=[
            {"from_email": "john@enron.com", "via_email_subject": "Project update", "to_email": "jane@enron.com"}
        ],
        result_count=1,
        strategy="person_connection"
    )

    payload = graph_extractor.extract(response)

    assert len(payload.nodes) == 2
    node_ids = {n.id for n in payload.nodes}
    assert node_ids == {"john@enron.com", "jane@enron.com"}

    assert len(payload.edges) == 1
    edge = payload.edges[0]
    assert edge.source == "john@enron.com"
    assert edge.target == "jane@enron.com"

def test_blocked_or_empty_retrieval():
    response = RetrievalResponse(
        query="show emails",
        intent="sent_emails",
        results=[],
        result_count=0,
        strategy="blocked_by_policy"
    )
    
    payload = graph_extractor.extract(response)
    assert len(payload.nodes) == 0
    assert len(payload.edges) == 0


def test_mcp_agent_rows_become_a_graph():
    from app.retrieval.graph_extractor import graph_extractor
    from app.retrieval.schemas import RetrievalResponse
    ranked = RetrievalResponse(query="q", intent="agent_query", strategy="mcp_agent", result_count=2, results=[
        {"executive": "Richard Shapiro", "title": "Vice President", "legal_email_count": 12},
        {"executive": "Steven J Kean", "title": "Vice President", "legal_email_count": 5},
    ])
    g = graph_extractor.extract(ranked)
    assert {n.label for n in g.nodes} == {"Results", "Richard Shapiro", "Steven J Kean"}
    assert all(e.source == "__results__" for e in g.edges) and g.edges[0].weight == 12.0

    emails = RetrievalResponse(query="q", intent="agent_query", strategy="mcp_agent", result_count=1, results=[
        {"sender": "kenneth.lay@enron.com", "sender_name": "Kenneth Lay", "emailId": "enron_1", "subject": "Board"},
    ])
    g = graph_extractor.extract(emails)
    assert {(n.type, n.label) for n in g.nodes} == {("Person", "Kenneth Lay"), ("Email", "Board")}
    assert [(e.source, e.target) for e in g.edges] == [("kenneth.lay@enron.com", "enron_1")]

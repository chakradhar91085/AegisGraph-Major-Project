from app.retrieval.graph_extractor import extract_graph
from app.retrieval.schemas import RetrievalResponse


def test_blocked_or_empty_retrieval():
    payload = extract_graph(RetrievalResponse(query="show emails", intent="agent_query", strategy="blocked_by_policy"))
    assert payload.nodes == [] and payload.edges == []


def test_mcp_agent_rows_become_a_graph():
    ranked = RetrievalResponse(query="q", intent="agent_query", strategy="mcp_agent", result_count=2, results=[
        {"executive": "Richard Shapiro", "title": "Vice President", "legal_email_count": 12},
        {"executive": "Steven J Kean", "title": "Vice President", "legal_email_count": 5},
    ])
    g = extract_graph(ranked)
    assert {n.label for n in g.nodes} == {"Results", "Richard Shapiro", "Steven J Kean"}
    assert all(e.source == "__results__" for e in g.edges) and g.edges[0].weight == 12.0

    emails = RetrievalResponse(query="q", intent="agent_query", strategy="mcp_agent", result_count=1, results=[
        {"sender": "kenneth.lay@enron.com", "sender_name": "Kenneth Lay", "emailId": "enron_1", "subject": "Board"},
    ])
    g = extract_graph(emails)
    assert {(n.type, n.label) for n in g.nodes} == {("Person", "Kenneth Lay"), ("Email", "Board")}
    assert [(e.source, e.target) for e in g.edges] == [("kenneth.lay@enron.com", "enron_1")]


def test_nodes_carry_the_rows_details():
    g = extract_graph(RetrievalResponse(query="q", intent="agent_query", strategy="mcp_agent", result_count=2, results=[
        {"sender": "Kenneth Lay", "emailId": "enron_1", "subject": "Board", "sent_on": "2001-01-02", "score": 0.8},
        {"name": "Sally Beck", "title": "Manager", "sent": 7, "embedding": None},
    ]))
    by_label = {n.label: n.details for n in g.nodes}
    assert by_label["Board"] == {"sender": "Kenneth Lay", "sent_on": "2001-01-02", "score": 0.8}
    assert by_label["Kenneth Lay"] == {}
    assert by_label["Sally Beck"] == {"title": "Manager", "sent": 7}


def test_overview_row_with_lists_becomes_a_graph():
    overview = RetrievalResponse(query="q", intent="agent_query", strategy="mcp_agent", result_count=1, results=[{
        "themes": [f"Theme {i}" for i in range(40)],
        "top_people": [{"name": "Jeff Dasovich", "title": "Employee", "sent": 5504}],
    }])
    g = extract_graph(overview)
    assert sum(n.type == "Theme" for n in g.nodes) == 10  # long lists are capped
    assert {"Results", "Jeff Dasovich"} <= {n.label for n in g.nodes}
    assert all(e.source == "__results__" for e in g.edges) and len(g.edges) == 11

    # List columns that are not people or themes must not add nodes to an email row.
    email = RetrievalResponse(query="q", intent="agent_query", strategy="mcp_agent", result_count=1, results=[
        {"emailId": "enron_1", "subject": "Board", "sensitivity": ["Legal", "HR"]},
    ])
    assert [n.type for n in extract_graph(email).nodes if n.type != "Query"] == ["Email"]

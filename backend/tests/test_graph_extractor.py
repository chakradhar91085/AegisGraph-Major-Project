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

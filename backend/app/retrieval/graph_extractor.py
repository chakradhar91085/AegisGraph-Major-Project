"""Builds the graph shown in the UI strictly from rows the user was already allowed to retrieve."""
import re
from typing import List, Optional
from pydantic import BaseModel
from app.retrieval.schemas import RetrievalResponse


class GraphNode(BaseModel):
    id: str
    label: str
    type: str


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str
    weight: Optional[float] = None


class GraphVisualizationPayload(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]


# A safe cap to ensure UI doesn't crash on very dense clusters even if policy allows them
VISUALIZATION_CAP = 25

_EMAIL = re.compile(r"[\w.%+-]+@[\w.-]+\.[a-z]{2,}", re.IGNORECASE)
# Column-name fragments the agent uses for people (sender, executive, recipient_name...).
_PERSON_KEYS = ("name", "sender", "recipient", "executive", "person", "employee", "contact", "author", "from", "to")


def extract_graph(response: RetrievalResponse) -> GraphVisualizationPayload:
    """Agent rows have whatever columns the LLM chose, so read them by shape:
    addresses and *name / sender / executive... columns are people, emailId/subject an
    email, *theme* a theme. Items in one row are linked; rows holding a single item
    (e.g. a ranked list of executives) hang off one 'Results' hub so they still connect."""
    nodes, edges = [], []
    hub = GraphNode(id="__results__", label="Results", type="Query")
    for row in response.results[:VISUALIZATION_CAP]:
        items = []
        for key, value in row.items():
            k = key.lower()
            if not isinstance(value, str) or not value.strip() or "subject" in k or "body" in k:
                continue
            if _EMAIL.fullmatch(value.strip()):
                items.append(GraphNode(id=value.strip().lower(), label=value.strip(), type="Person"))
            elif "theme" in k or "topic" in k:
                items.append(GraphNode(id=f"theme:{value}", label=value, type="Theme"))
            elif any(w in k for w in _PERSON_KEYS) and 2 <= len(value.split()) <= 5:
                items.append(GraphNode(id=value, label=value, type="Person"))
        email_id = row.get("emailId") or row.get("email_id")
        if email_id:
            items.append(GraphNode(id=str(email_id), label=str(row.get("subject") or "No Subject")[:60], type="Email"))
        # A person's address and name columns describe one person: keep the address, label it with the name.
        people = [n for n in items if n.type == "Person"]
        if len(people) == 2 and "@" in people[0].id and "@" not in people[1].id:
            people[0].label = people[1].label
            items.remove(people[1])
        elif len(people) == 2 and "@" in people[1].id and "@" not in people[0].id:
            people[1].label = people[0].label
            items.remove(people[0])
        nodes += items
        if len(items) == 1:
            nodes.append(hub)
            edges.append(GraphEdge(source=hub.id, target=items[0].id, type="FOUND",
                                   weight=next((float(v) for v in row.values() if isinstance(v, (int, float))
                                                and not isinstance(v, bool)), None)))
        for other in items[1:]:
            edges.append(GraphEdge(source=items[0].id, target=other.id, type="RELATED"))

    unique_edges = {(e.source, e.target, e.type): e for e in edges}
    return GraphVisualizationPayload(nodes=list({n.id: n for n in nodes}.values()), edges=list(unique_edges.values()))

"""Builds the graph shown in the UI strictly from rows the user was already allowed to retrieve."""
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from app.retrieval.schemas import RetrievalResponse


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    details: Dict[str, Any] = {}  # the row's other fields, shown when the node is clicked


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
_PERSON_KEYS = ("name", "sender", "recipient", "executive", "person", "people", "employee", "contact", "author", "from", "to")
_NESTED_CAP = 10


def _flat_rows(rows):
    """Overview-style rows hold lists (themes: [...], top_people: [{...}]); each entry becomes its own row."""
    for row in rows:
        yield row
        for key, value in row.items():
            for item in (value[:_NESTED_CAP] if isinstance(value, list) else [value] if isinstance(value, dict) else []):
                yield item if isinstance(item, dict) else {key: item}


def _details(row: dict, node: GraphNode) -> dict:
    """The row's readable fields, minus ids and whatever the node's own name already says."""
    details = {}
    for key, value in row.items():
        if key.lower().endswith("id") or value in (None, "", []) or isinstance(value, dict):
            continue
        if isinstance(value, list) and not all(isinstance(v, (str, int, float)) for v in value):
            continue
        if isinstance(value, str):
            if value.strip().lower() in (node.id.lower(), node.label.lower()):
                continue
            value = value[:300]
        details[key] = value
    return details


def extract_graph(response: RetrievalResponse) -> GraphVisualizationPayload:
    """Agent rows have whatever columns the LLM chose, so read them by shape:
    addresses and *name / sender / executive... columns are people, emailId/subject an
    email, *theme* a theme. Items in one row are linked; rows holding a single item
    (e.g. a ranked list of executives) hang off one 'Results' hub so they still connect."""
    nodes, edges = [], []
    hub = GraphNode(id="__results__", label="Results", type="Query")
    for row in _flat_rows(response.results):
        if len({n.id for n in nodes}) >= VISUALIZATION_CAP:
            break
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
        # The row describes its email if it has one, otherwise its first person or theme.
        if items:
            main = next((n for n in items if n.type == "Email"), items[0])
            main.details = _details(row, main)
        nodes += items
        if len(items) == 1:
            nodes.append(hub)
            edges.append(GraphEdge(source=hub.id, target=items[0].id, type="FOUND",
                                   weight=next((float(v) for v in row.values() if isinstance(v, (int, float))
                                                and not isinstance(v, bool)), None)))
        for other in items[1:]:
            edges.append(GraphEdge(source=items[0].id, target=other.id, type="RELATED"))

    # A node seen in several rows keeps the details from all of them.
    unique_nodes: Dict[str, GraphNode] = {}
    for n in nodes:
        if n.id in unique_nodes:
            n.details = {**unique_nodes[n.id].details, **n.details}
        unique_nodes[n.id] = n
    unique_edges = {(e.source, e.target, e.type): e for e in edges}
    return GraphVisualizationPayload(nodes=list(unique_nodes.values()), edges=list(unique_edges.values()))

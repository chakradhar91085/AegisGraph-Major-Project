"""
AegisGraph — deterministic masking for MEDIUM-risk responses.

Applied in code (not requested from the LLM): e-mail addresses, phone numbers,
SSNs and known person names are replaced before the context reaches the LLM,
and again on the LLM's answer and the graph payload.
"""
import re

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_PHONE = re.compile(r"(?<!\d)\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?!\d)")


def names_from_text(*texts: str) -> set[str]:
    """Person names implied by e-mail addresses, e.g. jeff.dasovich@x.com -> 'jeff dasovich'."""
    names = set()
    for text in texts:
        for address in _EMAIL.findall(text):
            parts = [p for p in re.split(r"[._]", address.split("@")[0]) if p.isalpha() and len(p) > 1]
            if len(parts) >= 2:
                names.add(" ".join(parts))
    return names


def names_from_records(rows) -> set[str]:
    """Person names stored in result rows, e.g. {'sender_name': 'Kenneth L. Lay'}."""
    names = set()
    for row in rows:
        for key, value in row.items():
            if "name" in key.lower() and isinstance(value, str) and "@" not in value and len(value.split()) >= 2:
                names.add(value)
    return names


def mask_text(text: str, names=()) -> str:
    text = _EMAIL.sub("[REDACTED_EMAIL]", text)
    text = _SSN.sub("[REDACTED_SSN]", text)
    text = _PHONE.sub("[REDACTED_PHONE]", text)
    for name in names:
        first, last = re.escape(name.split()[0]), re.escape(name.split()[-1])
        middle = r"(?:[\s,]+[A-Za-z]\.?)?"  # "Kenneth L. Lay", "Lay, Kenneth L."
        pattern = rf"\b{first}{middle}[\s,]+{last}\b|\b{last}[\s,]+{first}{middle}(?!\w)"
        text = re.sub(pattern, "[REDACTED_NAME]", text, flags=re.IGNORECASE)
    return text


def mask_graph(graph: dict, names=()) -> dict:
    """Pseudonymize Person nodes consistently and scrub other labels."""
    person_ids: dict[str, str] = {}
    nodes = []
    for node in graph.get("nodes", []):
        if node["type"] == "Person":
            new_id = person_ids.setdefault(node["id"], f"person-{len(person_ids) + 1}")
            nodes.append({**node, "id": new_id, "label": new_id.replace("-", " ").title()})
        else:
            nodes.append({**node, "label": mask_text(node["label"], names)})
    edges = [
        {**e, "source": person_ids.get(e["source"], e["source"]), "target": person_ids.get(e["target"], e["target"])}
        for e in graph.get("edges", [])
    ]
    return {"nodes": nodes, "edges": edges}

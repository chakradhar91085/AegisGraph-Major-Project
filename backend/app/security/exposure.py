"""
AegisGraph — sensitivity exposure (5th risk signal).

The other four signals describe HOW a user asks; this one measures WHAT they got.
Each retrieved email contributes  sensitivity_score x (0.5 + 0.5 x seniority),
where seniority is the most senior person on it (sender or recipient), so a CEO's HR
email counts fully and a junior employee's half. A person row with no email (a
profile lookup) contributes 0.3 x seniority. Scores come from the graph
(scripts/enrich_graph.py), looked up here by id, never from the LLM's own rows.
"""
import logging
import math
import re
from collections import Counter

from app.core.config import settings

logger = logging.getLogger(__name__)

_EMAIL = re.compile(r"[\w.%+-]+@[\w.-]+\.[a-z]{2,}", re.IGNORECASE)
_PROFILE_WEIGHT = 0.3
SENSITIVE_SCORE = 0.6  # Personal and above, or SSN/card/DOB


def _ids_and_people(results: list[dict]) -> tuple[list[str], list[str]]:
    ids, people = set(), set()
    for row in results:
        for key in ("emailId", "email_id", "id"):
            if isinstance(row.get(key), str) and row[key].startswith("enron_"):
                ids.add(row[key])
        for value in row.values():
            if isinstance(value, str) and _EMAIL.fullmatch(value.strip()):
                people.add(value.strip().lower())
    return sorted(ids), sorted(people)


async def measure(results: list[dict]) -> dict:
    """Exposure of one answer. Empty dict if nothing was retrieved or the graph is unreachable."""
    ids, people = _ids_and_people(results)
    if not ids and not people:
        return {}
    from app.db.neo4j import neo4j_client
    try:
        emails = await neo4j_client.execute_read("""
            MATCH (e:Email) WHERE e.emailId IN $ids
            OPTIONAL MATCH (s:Person)-[:SENT]->(e)
            OPTIONAL MATCH (e)-[:SENT_TO|CC_TO]->(r:Person)
            WITH e, max(coalesce(s.seniority, 0.0)) AS ss, max(coalesce(r.seniority, 0.0)) AS rs
            RETURN e.emailId AS id, coalesce(e.sensitivity_score, 0.0) AS score,
                   coalesce(e.sensitivity, []) AS labels, coalesce(e.pii, []) AS pii,
                   CASE WHEN ss > rs THEN ss ELSE rs END AS seniority""", {"ids": ids}) if ids else []
        persons = await neo4j_client.execute_read("""
            MATCH (p:Person) WHERE p.email IN $people
            RETURN p.email AS email, coalesce(p.seniority, 0.0) AS seniority""", {"people": people}) if people else []
    except Exception as e:
        logger.warning(f"Exposure lookup failed: {e}")
        return {}

    labels, pii = Counter(), Counter()
    units, sensitive_units, sensitive, top = 0.0, 0.0, 0, 0.0
    for e in emails:
        cost = e["score"] * (0.5 + 0.5 * e["seniority"])
        units += cost
        if e["score"] >= SENSITIVE_SCORE:  # a phone number alone (0.3) is not "sensitive"
            sensitive += 1
            sensitive_units += cost
        top = max(top, e["seniority"])
        labels.update(e["labels"])
        pii.update(e["pii"])
    if not ids:  # people only (e.g. "list the executives"): profile exposure
        for p in persons:
            units += _PROFILE_WEIGHT * p["seniority"]
            top = max(top, p["seniority"])
    else:
        top = max([top] + [p["seniority"] for p in persons])
    return {"units": round(units, 3), "sensitive_units": round(sensitive_units, 3), "sensitive_items": int(sensitive), "items": len(emails) or len(persons),
            "max_seniority": round(top, 2), "labels": dict(labels), "pii": dict(pii)}


def accumulate(previous: float, previous_at: float, now: float, units: float) -> float:
    """Fading total: halves every SECURITY_SENSITIVITY_HALF_LIFE_SECONDS, plus this answer."""
    if previous and previous_at:
        previous *= 0.5 ** ((now - previous_at) / settings.SECURITY_SENSITIVITY_HALF_LIFE_SECONDS)
    return previous + units


def signal(total: float) -> float:
    """S_sens = 1 - exp(-E / kappa), in [0, 1)."""
    return 1.0 - math.exp(-total / settings.SECURITY_SENSITIVITY_SCALE) if total > 0 else 0.0

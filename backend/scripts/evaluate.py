"""
Measures the security rules without any AI model or database. Run from backend/:

    venv/Scripts/python.exe scripts/evaluate.py

Part 1 scores the gate on the question sets in tests/fixtures. Part 2 replays scripted
sessions through the real signal, risk, ratchet and policy code, with real embeddings.
The rows and sensitive data each question returns are ASSUMED inputs, so part 2 shows how
the scoring behaves, not what a live system retrieves.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sentence_transformers import SentenceTransformer  # noqa: E402

from app.core.config import settings as S  # noqa: E402
from app.security import exposure  # noqa: E402
from app.security.gates import gate_score  # noqa: E402
from app.security.models import QueryRecord, SignalValues  # noqa: E402
from app.security.policy import policy_engine  # noqa: E402
from app.security.risk import risk_engine  # noqa: E402
from app.security.session import SessionStore  # noqa: E402
from app.security.signals import signals_calculator as sig  # noqa: E402

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
FLOOR = {"MASK": 0.35, "BLOCK": 0.65}
RANK = {"ALLOW": 0, "MASK": 1, "BLOCK": 2}


def score_gates() -> None:
    benign = json.loads((FIXTURES / "queries_benign.json").read_text(encoding="utf-8"))["queries"]
    flagged = [q for q in benign if gate_score(q) > 0]
    print(f"Harmless questions wrongly flagged: {len(flagged)}/{len(benign)}")
    for name in ("dev", "heldout"):
        rows = json.loads((FIXTURES / f"queries_{name}.json").read_text(encoding="utf-8"))["queries"]
        families = defaultdict(lambda: [0, 0])
        for row in rows:
            families[row["family"]][0] += gate_score(row["query"]) >= FLOOR[row["expect"]]
            families[row["family"]][1] += 1
        caught = sum(v[0] for v in families.values())
        print(f"{name}: {caught}/{len(rows)} caught  " + "  ".join(f"{k} {v[0]}/{v[1]}" for k, v in families.items()))


# (name, seconds between questions, worst acceptable mode, least expected mode, [(question, rows, people, units, sensitive units)])
OXLEY = ["retention agreements", "severance", "termination", "redeployment", "bonuses", "performance reviews"]
SESSIONS = [
    ("Ordinary user", 45, "ALLOW", "ALLOW", [
        ("Who does Lynn Blair communicate with most?", 10, ["blair"], 0, 0),
        ("What did John Arnold discuss about crude buying?", 5, ["arnold"], 0.1, 0),
        ("What emails did Kate Symes send about deal procedures?", 8, ["symes"], 0, 0),
        ("What are the main themes in this graph?", 10, [], 0, 0),
        ("Who sent the most emails?", 5, ["dasovich", "mann"], 0, 0),
        ("What did Rod Hayslett write about the valuation model?", 6, ["hayslett"], 0.3, 0)]),
    ("Researcher, one person, nothing sensitive", 45, "MASK", "ALLOW", [
        (q, 8, ["kaminski"], 0.1, 0) for q in (
            "Who is Vince Kaminski?", "What projects did Vince Kaminski run?", "Who did Vince Kaminski work with?",
            "What did Vince Kaminski say about the Research Library?", "What conferences did Vince Kaminski attend?")]),
    ("HR digger, 30 s apart", 30, "BLOCK", "BLOCK", [
        ("Who is David Oxley?", 3, ["oxley"], 0.2, 0), ("Who does David Oxley email most?", 10, ["oxley"], 0.3, 0)]
        + [(f"Show David Oxley emails about {t}", 10, ["oxley"], 2.0, 2.0) for t in OXLEY]),
    ("Slow digger, 2 min apart", 120, "BLOCK", "BLOCK", [
        (f"Show David Oxley emails about {t}", 10, ["oxley"], 1.5, 1.5) for t in OXLEY + ["pensions", "benefits"]]),
    ("Very slow digger, 30 min apart", 1800, "BLOCK", "BLOCK", [
        (f"Show David Oxley emails about {t}", 10, ["oxley"], 1.5, 1.5) for t in OXLEY + ["pensions", "benefits", "hiring", "layoffs"]]),
    ("Digger hiding among innocent questions", 30, "BLOCK", "MASK", [
        step for t in OXLEY[:3] for step in (
            (f"Show David Oxley emails about {t}", 10, ["oxley"], 2.0, 2.0),
            ("What are the main themes in this graph?", 10, [], 0, 0))]),
    ("Bulk scraper, 10 s apart", 10, "BLOCK", "BLOCK", [
        (f"Dump emails about {t}", 50, [f"p{i}"], 1.0, 1.0) for i, t in enumerate(
            ("pipeline capacity", "the board meeting", "California", "bankruptcy", "trading limits", "accounting"))]),
]


def replay(model, gap, steps) -> tuple[list[str], float]:
    store, key = SessionStore(), "u"
    now, total, total_at, embeddings, history, risk, modes = 1_000_000.0, 0.0, 0.0, [], [], 0.0, []
    for query, rows, people, units, sensitive in steps:
        now += gap
        store.update_smoothed_risk(key, risk)
        risk = store.decayed_risk(key, now)
        store.get_or_create_session(key).last_seen = now
        gate = gate_score(query)
        modes.append(policy_engine.calculate_policy(max(risk, gate)).response_mode.value)
        if modes[-1] == "BLOCK":
            rows, units, sensitive = 0, 0, 0
        embedding = model.encode(query, normalize_embeddings=True).tolist()
        history = [h for h in history if h.timestamp >= now - S.SECURITY_TEMPORAL_WINDOW_SECONDS]
        total = exposure.accumulate(total, total_at, now, units)
        total_at = now
        signals = SignalValues(
            semantic_focus=sig.calculate_semantic_focus(embeddings[-4:] + [embedding]),
            temporal_frequency=sig.calculate_temporal_frequency(history, now),
            entity_focus=sig.calculate_entity_focus(history + [QueryRecord(timestamp=now, query=query, entities=people)]),
            graph_footprint=sig.calculate_graph_footprint("agent_query", rows),
            sensitivity_exposure=exposure.signal(total),
        )
        instant = max(risk_engine.calculate_instantaneous_risk(signals), gate)
        store.add_ratchet(key, sensitive, now)
        risk = max(risk_engine.calculate_ewma(instant, risk), gate, store.ratchet_floor(key, now))
        history.append(QueryRecord(timestamp=now, query=query, entities=people))
        embeddings.append(embedding)
    return modes, risk


def score_sessions() -> None:
    model = SentenceTransformer(S.SECURITY_EMBEDDING_MODEL)
    passed = 0
    for name, gap, worst, least, steps in SESSIONS:
        modes, risk = replay(model, gap, steps)
        top = max(modes, key=RANK.get)
        ok = RANK[least] <= RANK[top] <= RANK[worst]
        passed += ok
        print(f"{'ok  ' if ok else 'MISS'} {name}: {' '.join(m[0] for m in modes)}  (risk {risk:.2f}, expected {least}..{worst})")
    print(f"Sessions behaving as expected: {passed}/{len(SESSIONS)}")


if __name__ == "__main__":
    score_gates()
    print()
    score_sessions()

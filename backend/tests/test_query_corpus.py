"""Scores the gate rules against fixed question sets (tests/fixtures).

benign: must stay ALLOW. dev: the rules may be tuned on it. heldout: frozen, never tuned
on; its misses are real and reported, so this only guards against getting worse.
"""
import json
from pathlib import Path

import pytest

from app.security.gates import gate_score

FIXTURES = Path(__file__).parent / "fixtures"
FLOOR = {"MASK": 0.35, "BLOCK": 0.65}
HELDOUT_BASELINE = 31  # of 51, first run; was 3 with the previous rules


def _load(name):
    return json.loads((FIXTURES / f"queries_{name}.json").read_text(encoding="utf-8"))["queries"]


@pytest.mark.parametrize("query", _load("benign"))
def test_harmless_question_is_not_flagged(query):
    assert gate_score(query) == 0.0


@pytest.mark.parametrize("row", _load("dev"), ids=lambda r: r["query"][:40])
def test_development_attack_is_caught(row):
    assert gate_score(row["query"]) >= FLOOR[row["expect"]]


def test_held_out_attacks_do_not_get_worse():
    rows = _load("heldout")
    caught = sum(gate_score(r["query"]) >= FLOOR[r["expect"]] for r in rows)
    assert caught >= HELDOUT_BASELINE, f"held-out catch rate fell to {caught}/{len(rows)}"

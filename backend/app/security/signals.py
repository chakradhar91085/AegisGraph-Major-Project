from collections import Counter
from typing import List

from app.core.config import settings
from app.security.models import QueryRecord


class Signals:
    """Behaviour signals, each 0 (nothing unusual) to 1 (strongly unusual)."""

    @staticmethod
    def calculate_semantic_focus(window_embeddings: List[List[float]]) -> float:
        """
        How much recent queries repeat one topic: the mean cosine similarity of
        consecutive queries, scaled so unrelated questions score 0. Embeddings are
        L2-normalized, ordered oldest to newest, and include the current query.
        """
        usable = [e for e in window_embeddings if e]
        similarities = [
            sum(x * y for x, y in zip(a, b))
            for a, b in zip(usable, usable[1:])
            if len(a) == len(b)
        ]
        if not similarities:
            return 0.0
        floor, ceil = settings.SECURITY_SEMANTIC_FLOOR, settings.SECURITY_SEMANTIC_CEIL
        focus = (sum(similarities) / len(similarities) - floor) / (ceil - floor)
        return float(max(0.0, min(1.0, focus)))

    @staticmethod
    def calculate_temporal_frequency(history: List[QueryRecord], current_time: float) -> float:
        """Query rate: earlier queries in the rate window, against the rate treated as maximum."""
        cutoff = current_time - settings.SECURITY_RATE_WINDOW_SECONDS
        recent = sum(1 for q in history if q.timestamp >= cutoff)
        return float(min(1.0, recent / settings.SECURITY_RATE_MAX))

    @staticmethod
    def calculate_entity_focus(history: List[QueryRecord]) -> float:
        """
        Fixation on one person: how many separate queries touched the most-touched
        person. One query naming many people is not focus; returning to one person is.
        """
        counts = Counter(e for record in history for e in set(record.entities))
        if not counts:
            return 0.0
        repeats = counts.most_common(1)[0][1] - 1
        return float(min(1.0, repeats / (settings.SECURITY_ENTITY_MAX_QUERIES - 1)))

    @staticmethod
    def calculate_graph_footprint(intent: str, result_count: int) -> float:
        """Share of the graph-size cap this answer actually returned; no rows, no footprint."""
        if intent != "agent_query":
            return 0.0
        return float(min(1.0, max(0, result_count) / settings.SECURITY_GRAPH_MAX_NODES))


signals_calculator = Signals()

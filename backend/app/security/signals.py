import math
from typing import List, Optional
from app.core.config import settings
from app.security.models import QueryRecord
import logging

logger = logging.getLogger(__name__)

class Signals:
    @staticmethod
    def calculate_semantic_focus(window_embeddings: List[List[float]]) -> float:
        """
        S_sem(t) = 1/(|W|-1) * sum of cos(q_{t-i}, q_{t-i-1}) over consecutive
        pairs in a sliding window W of recent query embeddings (paper Eq. 1).

        A HIGH value means recent queries are semantically similar to each
        other — i.e. the user is repeatedly circling the same topic, which is
        the focused-probing behavior this signal exists to catch. This is the
        opposite direction from "drift" (topic change), which is why this is
        no longer named/interpreted as drift.

        window_embeddings must be ordered oldest -> newest and should include
        the current query's embedding as the last element. Embeddings are
        assumed L2-normalized, so cosine similarity is just the dot product.

        Raw cosine similarity is in [-1, 1]; linearly remapped to [0, 1] so
        this signal is on the same scale as the other three (high = risk).
        Returns 0.0 when there's insufficient history to form a pair.
        """
        usable = [e for e in window_embeddings if e]
        if len(usable) < 2:
            return 0.0

        similarities = []
        for i in range(len(usable) - 1):
            a, b = usable[i], usable[i + 1]
            if len(a) != len(b):
                continue
            dot_product = sum(x * y for x, y in zip(a, b))
            dot_product = max(-1.0, min(1.0, dot_product))
            similarities.append(dot_product)

        if not similarities:
            return 0.0

        mean_similarity = sum(similarities) / len(similarities)
        focus = (mean_similarity + 1.0) / 2.0
        return float(max(0.0, min(1.0, focus)))

    @staticmethod
    def calculate_temporal_frequency(prev_timestamp: Optional[float], current_time: float) -> float:
        """
        S_temp(t) = exp(-alpha_temp * delta_tau_t), where delta_tau_t is the
        gap in seconds since the previous query (paper Eq. 2). Rapid-fire
        queries push this toward 1.0; normal human pacing decays it toward 0.

        Returns 0.0 for the first query of a session (no prior query to
        measure a gap against).
        """
        if prev_timestamp is None:
            return 0.0

        delta_tau = max(0.0, current_time - prev_timestamp)
        alpha = settings.SECURITY_ALPHA_TEMP
        S_temp = math.exp(-alpha * delta_tau)
        return float(max(0.0, min(1.0, S_temp)))

    @staticmethod
    def calculate_entity_focus(history: List[QueryRecord]) -> float:
        """
        S_ent(t) = 1 - H(E_t) / log(|E_t| + epsilon)
        H is entropy.
        """
        # Collect all entities in the window
        all_entities = []
        for rec in history:
            all_entities.extend(rec.entities)
            
        if len(all_entities) < 2:
            return 0.0 # Insufficient history for entity concentration
            
        unique_entities = set(all_entities)
        total = float(len(all_entities))

        # Persistence factor (paper Eq. 5): a couple of mentions of one person is
        # normal use, so concentration only reaches full weight after 4 mentions.
        persistence = min(1.0, total / 4.0)

        # If exactly 1 unique entity, entropy is 0, so concentration is full
        if len(unique_entities) == 1:
            return persistence
            
        # Calculate entropy
        entropy = 0.0
        for e in unique_entities:
            p = all_entities.count(e) / total
            if p > 0:
                entropy -= p * math.log(p)
                
        # Normalize
        epsilon = 1e-9
        max_entropy = math.log(len(unique_entities) + epsilon)
        
        if max_entropy <= 0:
            return persistence
            
        focus = (1.0 - (entropy / max_entropy)) * persistence
        return float(max(0.0, min(1.0, focus)))

    @staticmethod
    def calculate_graph_footprint(intent: str, result_count: int) -> float:
        """
        S_graph(t) = (d_t / d_max) + eta * (v_t / v_max)
        """
        if intent != "agent_query":
            return 0.0

        d_t = 3  # free-form agent Cypher has no known depth; its rows still count via result_count
        v_t = result_count
        
        d_max = float(settings.SECURITY_GRAPH_MAX_DEPTH)
        v_max = float(settings.SECURITY_GRAPH_MAX_NODES)
        eta = settings.SECURITY_GRAPH_WEIGHT
        
        if d_max <= 0 or v_max <= 0:
            return 0.0
            
        depth_term = d_t / d_max
        volume_term = eta * (v_t / v_max)
        
        val = depth_term + volume_term
        return float(max(0.0, min(1.0, val)))

signals_calculator = Signals()

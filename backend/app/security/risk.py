from app.core.config import settings
from app.security.models import SignalValues

class RiskEngine:
    @staticmethod
    def calculate_instantaneous_risk(signals: SignalValues) -> float:
        """
        R_t = alpha * S_sem + beta * S_temp + gamma * S_ent + delta * S_graph + epsilon * S_sens
        """
        alpha = settings.SECURITY_WEIGHT_SEMANTIC
        beta = settings.SECURITY_WEIGHT_TEMPORAL
        gamma = settings.SECURITY_WEIGHT_ENTITY
        delta = settings.SECURITY_WEIGHT_GRAPH
        epsilon = settings.SECURITY_WEIGHT_SENSITIVITY

        # Ensure weights sum to 1.0 (approximately)
        total_weight = alpha + beta + gamma + delta + epsilon
        if total_weight <= 0:
            return 0.0

        r_t = (
            (alpha * signals.semantic_focus) +
            (beta * signals.temporal_frequency) +
            (gamma * signals.entity_focus) +
            (delta * signals.graph_footprint) +
            (epsilon * signals.sensitivity_exposure)
        ) / total_weight
        
        return float(max(0.0, min(1.0, r_t)))

    @staticmethod
    def calculate_ewma(instantaneous_risk: float, prev_smoothed: float) -> float:
        """
        Gamma_t = lambda * R_t + (1 - lambda) * Gamma_{t-1}
        """
        lam = settings.SECURITY_EWMA_LAMBDA
        lam = max(0.0, min(1.0, lam))
        
        smoothed = (lam * instantaneous_risk) + ((1.0 - lam) * prev_smoothed)
        return float(max(0.0, min(1.0, smoothed)))

risk_engine = RiskEngine()

from app.core.config import settings
from app.security.models import SignalValues

class RiskEngine:
    @staticmethod
    def calculate_instantaneous_risk(signals: SignalValues) -> float:
        """
        Noisy-OR: R_t = 1 - product(1 - evidence_i).
        Zero signals give zero risk, one strong signal counts on its own, and
        several compound without ever passing 1. Repeating a person's name raises
        both topic and person focus, so those count once, as the stronger of the two.
        """
        focus = max(settings.SECURITY_WEIGHT_SEMANTIC * signals.semantic_focus,
                    settings.SECURITY_WEIGHT_ENTITY * signals.entity_focus)
        safe = 1.0 - focus
        for evidence in (
            settings.SECURITY_WEIGHT_TEMPORAL * signals.temporal_frequency,
            settings.SECURITY_WEIGHT_GRAPH * signals.graph_footprint,
            settings.SECURITY_WEIGHT_SENSITIVITY * signals.sensitivity_exposure,
        ):
            safe *= 1.0 - evidence
        return float(max(0.0, min(1.0, 1.0 - safe)))

    @staticmethod
    def calculate_ewma(instantaneous_risk: float, prev_smoothed: float) -> float:
        """Gamma_t = lam * R_t + (1 - lam) * Gamma_{t-1}, with a faster lam going up than down."""
        lam = settings.SECURITY_EWMA_RISE if instantaneous_risk > prev_smoothed else settings.SECURITY_EWMA_FALL
        smoothed = (lam * instantaneous_risk) + ((1.0 - lam) * prev_smoothed)
        return float(max(0.0, min(1.0, smoothed)))

risk_engine = RiskEngine()

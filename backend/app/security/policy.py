import math
from app.core.config import settings
from app.security.models import AdaptivePolicy, RiskLevel, ResponseMode

# Static Role Policies.
ROLE_POLICIES = {
    "Auditor": {"max_context_limit": 50, "max_graph_depth": 5},
    "Analyst": {"max_context_limit": 30, "max_graph_depth": 3},
    "Standard": {"max_context_limit": 10, "max_graph_depth": 2},
}

class PolicyEngine:
    @staticmethod
    def calculate_policy(ewma_risk: float, role: str = "Standard") -> AdaptivePolicy:
        """
        Calculate adaptive response policy parameters based on the smoothed risk score (Gamma_bar_t) and user role.
        
        kappa_t = 1 - 1 / (1 + exp(-theta_slope * (Gamma_bar_t - theta_mid)))
        k_eff = max(1, floor(kappa_t * k_baseline))
        d_eff = max(0, floor(kappa_t * d_baseline))
        """
        theta_mid = settings.SECURITY_THETA_MID
        theta_slope = settings.SECURITY_THETA_SLOPE
        
        # Determine discrete risk level.
        # Bands match the paper's Appendix A.2 (moderate: 0.35 <= risk < 0.65).
        if ewma_risk < 0.35:
            level = RiskLevel.LOW
        elif ewma_risk < 0.65:
            level = RiskLevel.MEDIUM
        else:
            level = RiskLevel.HIGH
            
        # Calculate attenuation factor (kappa_t) using sigmoid
        exponent = -theta_slope * (ewma_risk - theta_mid)
        
        try:
            sigmoid_val = 1.0 / (1.0 + math.exp(exponent))
        except OverflowError:
            sigmoid_val = 0.0 if exponent > 0 else 1.0
            
        kappa_t = 1.0 - sigmoid_val
        
        # Clamp attenuation factor safely
        kappa_t = float(max(0.0, min(1.0, kappa_t)))
        
        # Baselines are taken from role static policy bounded by system max
        role_policy = ROLE_POLICIES.get(role, ROLE_POLICIES["Standard"])
        k_baseline = float(min(settings.MAX_RECORDS, role_policy["max_context_limit"]))
        d_baseline = float(min(settings.SECURITY_GRAPH_MAX_DEPTH, role_policy["max_graph_depth"]))
        
        # Effective constraints.
        # Rounded (not floored) so a low-risk session at a small baseline
        # (e.g. Standard role, d_baseline=1) isn't permanently truncated to
        # zero access even when kappa_t is near its 1.0 ceiling.
        k_eff = max(1, round(kappa_t * k_baseline))
        d_eff = max(0, round(kappa_t * d_baseline))
        
        # Determine Response Mode
        if level == RiskLevel.HIGH:
            response_mode = ResponseMode.BLOCK
        elif level == RiskLevel.MEDIUM:
            # Every role is masked at MEDIUM; privilege never reduces scrutiny.
            response_mode = ResponseMode.MASK
        else:
            response_mode = ResponseMode.ALLOW
        
        return AdaptivePolicy(
            risk_score=ewma_risk,
            risk_level=level,
            attenuation_factor=kappa_t,
            effective_context_limit=k_eff,
            effective_graph_depth=d_eff,
            response_mode=response_mode
        )

policy_engine = PolicyEngine()

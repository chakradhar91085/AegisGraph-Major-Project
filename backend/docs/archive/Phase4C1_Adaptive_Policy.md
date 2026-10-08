# Phase 4C.1 — Adaptive Policy

## 1. AdaptivePolicy Model

The `AdaptivePolicy` represents the calculated security restrictions applied to a specific query based on the session's risk level.

```python
class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class AdaptivePolicy(BaseModel):
    risk_score: float = Field(..., ge=0.0, le=1.0)
    risk_level: RiskLevel
    attenuation_factor: float = Field(..., ge=0.0, le=1.0)
    effective_context_limit: int = Field(..., ge=1)
    effective_graph_depth: int = Field(..., ge=0)
```

## 2. Policy Calculation (PolicyEngine)

The `PolicyEngine` (`app/security/policy.py`) translates the EWMA smoothed risk (`Γ̄_t`) into the `AdaptivePolicy`.

### Attenuation Factor (κ_t)

The core mechanism is a sigmoid-based attenuation factor that smoothly scales down information exposure as risk rises.

```
κ_t = 1 - 1 / (1 + exp(-θ_slope × (Γ̄_t - θ_mid)))
```

Where:
- `Γ̄_t`: Smoothed EWMA risk score
- `θ_mid`: Midpoint of the sigmoid curve (default: 0.55, via `SECURITY_THETA_MID`)
- `θ_slope`: Steepness of the sigmoid curve (default: 10.0, via `SECURITY_THETA_SLOPE`)

**Behavior**:
- When `Γ̄_t` is near 0.0, `κ_t` is close to 1.0 (minimal attenuation).
- When `Γ̄_t` equals `θ_mid`, `κ_t` is exactly 0.5.
- When `Γ̄_t` approaches 1.0, `κ_t` approaches 0.0 (maximum attenuation).

*Implementation detail*: Overflow errors are caught and handled if `exp()` grows too large, clamping the sigmoid to 0.0 or 1.0. The final `κ_t` is strictly bounded to `[0.0, 1.0]`.

### Effective Limits

The attenuation factor scales the baseline configurations to produce the effective limits for the query:

```python
k_eff = max(1, math.floor(kappa_t * k_baseline))
d_eff = max(0, math.floor(kappa_t * d_baseline))
```

- `k_baseline`: `settings.MAX_RECORDS` (default: 20)
- `d_baseline`: `settings.SECURITY_GRAPH_MAX_DEPTH` (default: 5)

Notice that `k_eff` has a floor of 1 (to permit minimal context if allowed), while `d_eff` has a floor of 0.

## 3. Discrete Risk Levels

The continuous EWMA risk is binned into discrete levels for reporting and high-level logic:

| EWMA Range | Risk Level | Behavior |
|:---|:---|:---|
| [0.0, 0.3) | LOW | `κ_t` ≈ 1.0. Context limit ≈ 20, Depth ≈ 5. Normal operation. |
| [0.3, 0.7) | MEDIUM | `κ_t` drops from ~0.9 to ~0.1. Limits are progressively scaled down. |
| [0.7, 1.0] | HIGH | `κ_t` < 0.1. Context limit clamped to 1. Depth clamped to 0. |

## 4. Policy Tests

The policy test suite (`tests/test_policy.py`) verifies:
- Correct mapping of EWMA to `RiskLevel` (LOW, MEDIUM, HIGH)
- Policy formula constraints (`κ_t` in bounds, limits properly floored)
- Monotonic decrease of `κ_t` as risk increases

## 5. Limitations

1. **Fixed thresholds**: `θ_mid` and `θ_slope` are static configuration values, not dynamically tuned.
2. **Global baselines**: The baseline limits (`k_baseline`, `d_baseline`) are global settings, rather than user-specific or role-specific baselines.
3. **Hard boundaries**: The strict `[0.3, 0.7)` boundaries for discrete risk levels may not reflect the nuanced decay of the continuous sigmoid curve.

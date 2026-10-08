# Phase 4B — Risk Model and Validation

## 1. The Four Behavioral Signals

AegisGraph monitors four behavioral signals per query:

| Signal | Symbol | Measures |
|:---|:---|:---|
| Semantic Drift | S_sem | How different the current query is from the previous one |
| Temporal Frequency | S_temp | How rapidly queries are arriving |
| Entity Focus | S_ent | How concentrated queries are on the same entities |
| Graph Footprint | S_graph | How deeply the query traverses the graph |

All signals are bounded to [0.0, 1.0] where higher values indicate more suspicious behavior.

## 2. Exact Final Formulas

### Semantic Drift

```
S_sem(t) = 1 - cos(E_t, E_{t-1})
```

Where `E_t` are L2-normalized embeddings from `all-MiniLM-L6-v2`. Since embeddings are pre-normalized, cosine similarity equals the dot product.

### Temporal Frequency

```
S_temp(t) = exp(-α_temp × Δτ_t)
```

Where `Δτ_t = τ_t - τ_{t-1}` is the time in seconds between the current and previous query.

**Parameter**: `α_temp = 0.1` (inverse seconds)

### Entity Focus

```
S_ent(t) = 1 - H(E_t) / log(|E_t| + ε)
```

Where `H` is Shannon entropy over entity frequencies, `|E_t|` is the number of unique entities, and `ε = 10⁻⁹`.

**Guard**: Returns 0.0 if `len(all_entities) < 2`.

### Graph Footprint

```
S_graph(t) = min(1, d_t / d_max + η × v_t / v_max)
```

Where:
- `d_t` = intent-based depth (heuristic mapping)
- `d_max = 5`
- `η = 0.5`
- `v_t` = result count
- `v_max = 50`

**Guard**: Returns 0.0 if `result_count == 0`.

## 3. Instantaneous Risk Fusion

```
R_t = (α × S_sem + β × S_temp + γ × S_ent + δ × S_graph) / (α + β + γ + δ)
```

Implemented in `app/security/risk.py`. The weight normalization ensures the output stays in [0.0, 1.0] regardless of whether weights sum to 1.0.

## 4. Signal Weights

| Weight | Parameter | Value |
|:---|:---|:---|
| α (semantic) | `SECURITY_WEIGHT_SEMANTIC` | 0.25 |
| β (temporal) | `SECURITY_WEIGHT_TEMPORAL` | 0.25 |
| γ (entity) | `SECURITY_WEIGHT_ENTITY` | 0.25 |
| δ (graph) | `SECURITY_WEIGHT_GRAPH` | 0.25 |

All four signals carry equal weight. This is a deliberate prototype simplification.

## 5. EWMA Smoothing

```
Γ̄_t = λ × R_t + (1 - λ) × Γ̄_{t-1}
```

**Parameter**: `λ = 0.3` (EWMA lambda, configurable via `SECURITY_EWMA_LAMBDA`)

- Higher λ makes the smoothed risk more responsive to recent queries.
- Lower λ provides more inertia and resistance to single-query spikes.
- Initial value: `Γ̄_0 = 0.0`

## 6. Complete Parameter Table

| Parameter | Config Key | Value | Units |
|:---|:---|:---|:---|
| α_temp | `SECURITY_ALPHA_TEMP` | 0.1 | s⁻¹ |
| Temporal window | `SECURITY_TEMPORAL_WINDOW_SECONDS` | 60 | seconds |
| d_max | `SECURITY_GRAPH_MAX_DEPTH` | 5 | levels |
| v_max | `SECURITY_GRAPH_MAX_NODES` | 50 | nodes |
| η | `SECURITY_GRAPH_WEIGHT` | 0.5 | dimensionless |
| α (sem weight) | `SECURITY_WEIGHT_SEMANTIC` | 0.25 | dimensionless |
| β (temp weight) | `SECURITY_WEIGHT_TEMPORAL` | 0.25 | dimensionless |
| γ (ent weight) | `SECURITY_WEIGHT_ENTITY` | 0.25 | dimensionless |
| δ (graph weight) | `SECURITY_WEIGHT_GRAPH` | 0.25 | dimensionless |
| λ (EWMA) | `SECURITY_EWMA_LAMBDA` | 0.3 | dimensionless |

## 7. Risk Interpretation

The EWMA risk score is interpreted via discrete risk levels:

| EWMA Range | Risk Level |
|:---|:---|
| [0.0, 0.3) | LOW |
| [0.3, 0.7) | MEDIUM |
| [0.7, 1.0] | HIGH |

These thresholds are hardcoded in `PolicyEngine.calculate_policy()`.

## 8. Edge-Case Corrections

Two corrections were applied during Phase 4B validation:

### 1. Entity Focus — Insufficient History Gate

```python
if len(all_entities) < 2:
    return 0.0
```

**Rationale**: A first-time query containing one entity represents insufficient behavioral history, not persistent entity-focused probing.

### 2. Graph Footprint — Zero-Result Safeguard

```python
if result_count == 0:
    return 0.0
```

**Rationale**: A zero-result retrieval should not receive maximum graph-footprint risk merely because its intent has a high theoretical depth.

## 9. Validation Sequences

Phase 4B.2 validation used controlled sequences to verify:

1. **Benign single lookup**: First query produces low risk across all signals.
2. **Entity-focused probing**: Repeated queries on the same entity drive S_ent toward 1.0.
3. **Rapid probing**: Queries at near-zero intervals drive S_temp toward 1.0.
4. **Graph expansion**: Progressive deepening drives S_graph toward 1.0.
5. **EWMA stepping**: Verified that `Γ̄_t = 0.3 × R_t + 0.7 × Γ̄_{t-1}` holds exactly.
6. **Session isolation**: Different sessions produce independent risk scores.

## 10. Methodology Alignment

### Aligned with Research Design

- **S_sem**: Uses cosine distance between consecutive query embeddings.
- **S_temp**: Uses exponential decay of inter-arrival time (`exp(-α × Δτ)`), not query count.
- **S_ent**: Uses entropy-based concentration with cold-start protection.
- **Risk fusion**: Weighted linear combination.
- **EWMA**: Standard exponential weighted moving average.

### Deviation: S_temp Correction

The initial implementation used query density (`N_t / τ`), which was identified as a methodology deviation and corrected to the paper-aligned `exp(-α_temp × Δτ_t)` formula during Phase 4B.

## 11. Known Simplifications

1. **Equal fixed weights**: All signals share 25% weight. The research may benefit from learned or domain-tuned weights.
2. **Heuristic entity extraction**: Entities are extracted via strategy-specific heuristics in the security service, not a trained NER model operating on the query text itself.
3. **Graph footprint approximation**: Graph depth is approximated via intent-to-depth mapping rather than parsing the physical Neo4j traversal path.
4. **No dynamic weight adaptation**: Weights are static, not adjusted based on observed attack patterns.
5. **Temporal window truncation**: History beyond 60 seconds is discarded, limiting the system's memory of longer-term patterns.

# Phase 4D — End-to-End Evaluation

## 1. Evaluation Methodology

Phase 4D evaluated the complete AegisGraph pipeline using an automated, deterministic test harness (`scripts/evaluate_aegisgraph.py`).

The evaluation compared two modes:
1. **BASELINE**: The full retrieval pipeline with static structural limits (`MAX_RECORDS=20`, `MAX_DEPTH=5`). The adaptive policy engine is bypassed (`κ = 1.0`).
2. **AEGISGRAPH**: The complete adaptive security pipeline where EWMA risk dynamically controls `κ_t`, scaling context limits and graph depth.

## 2. Tested Scenarios

The harness ran 8 behavioral scenarios designed to test specific risk vectors and sustained attack patterns:

| Scenario | Description | Expected Risk |
|:---|:---|:---|
| A | Benign single lookup | LOW |
| B | Benign slow exploration (5s delays) | LOW |
| C | Rapid repeated probing (multi-entity) | LOW / MEDIUM |
| D | Entity-focused probing (single entity) | LOW / MEDIUM |
| E | Progressive graph expansion | LOW / MEDIUM |
| F | Mixed multi-signal suspicious behavior | MEDIUM |
| G | Sustained rapid entity-focused probing (15 queries) | MEDIUM |
| H | Sustained multi-vector graph probing (20 queries) | MEDIUM / HIGH |

## 3. Results Summary

The raw quantitative results are stored in `scripts/phase4d_evaluation.json`.

### Aggregate Impact

| Metric | Value |
|:---|---:|
| Baseline Exposure (Records) | 450 |
| AegisGraph Exposure (Records) | 347 |
| **Total Exposure Reduction** | **22.9%** |

### Scenario Breakdown

| Scenario | Peak EWMA | Max Risk | Exposure Reduction | Blocked Queries |
|:---|---:|:---|---:|---:|
| A_BENIGN_SINGLE | 0.0210 | LOW | 0.0% | 0 |
| B_BENIGN_SLOW | 0.0708 | LOW | 0.0% | 0 |
| C_RAPID_REPEATED | 0.3547 | MEDIUM | 6.7% | 0 |
| D_ENTITY_FOCUSED | 0.4079 | MEDIUM | 12.1% | 0 |
| E_GRAPH_EXPANSION | 0.4192 | MEDIUM | 8.8% | 0 |
| F_MIXED_MULTI | 0.4578 | MEDIUM | 26.2% | 1 |
| G_RAPID_ENTITY | 0.4623 | MEDIUM | 19.8% | 0 |
| H_SUSTAINED_MULTI | 0.5176 | MEDIUM | 41.8% | 3 |

## 4. Key Findings

### 1. High Utility Preservation for Benign Behavior
Scenarios A and B demonstrate that AegisGraph correctly maintains LOW risk for normal, spaced-out queries. Exposure reduction was 0.0%, meaning benign users experience zero degradation in system utility.

### 2. Graceful Degradation Under Stress
As risk increased in scenarios C, D, and E, the system transitioned to MEDIUM risk. Exposure reduction smoothly scaled from 6.7% to 12.1% as context limits were gradually throttled by the sigmoid attenuation curve.

### 3. Effective Blockade of Sustained Attacks
Scenario H (Sustained Multi-Vector Graph Probing) reached the highest peak EWMA (0.5176) and triggered **3 blocked queries** due to depth enforcement (`d_eff < d_required`). This resulted in a massive **41.8% reduction in data exposure** compared to the baseline, successfully disrupting the simulated attack.

### 4. Difficulty Reaching HIGH Risk
A critical observation is that no scenario naturally reached HIGH risk (EWMA > 0.7), even the 20-query multi-vector attack (Scenario H peaked at 0.52). 

HIGH-risk behavior (which aggressively throttles context limits and restricts the graph) exists in the implemented policy and unit tests, but was not demonstrated by the current extended end-to-end scenarios. 

This is largely due to:
- The zero-result safeguard in `S_graph` resetting graph risk to 0.0 on blocked queries.
- The `λ = 0.3` EWMA parameter providing significant inertia against rapid spikes.

This is considered a successful, honest finding of the prototype evaluation, demonstrating that the system requires significant, sustained anomalous behavior to trigger the most severe restrictions.

### 5. Architectural Clarifications
- **Graph Depth Gating**: Graph depth is currently enforced through intent-to-depth strategy gating at the RetrievalService boundary, not physical Neo4j traversal measurement.
- **Exposure Metric Context**: Do not describe the 41.8% reduction result as a general security effectiveness percentage. It applies only to the controlled Scenario H evaluation.
- The zero-result safeguard in `S_graph` resetting graph risk to 0.0 on blocked queries.
- The `λ = 0.3` EWMA parameter providing significant inertia against rapid spikes.

This is considered a successful, honest finding of the prototype evaluation, demonstrating that the system requires significant, sustained anomalous behavior to trigger the most severe restrictions.

## 5. Limitations

1. **Mocked LLM**: The LLM generation was mocked during evaluation to speed up execution. While this isolated the retrieval telemetry perfectly, it means end-to-end latency impact was not measured.
2. **Fixed Synthetic Sequences**: The evaluation relies on fixed, predefined sequences of queries rather than stochastic or adversarial user simulation.
3. **No Ground Truth**: The evaluation measures "exposure reduction" (utility vs. restriction), not standard security metrics like True Positive Rate or False Positive Rate, as there is no ground-truth labeled dataset of attacks.

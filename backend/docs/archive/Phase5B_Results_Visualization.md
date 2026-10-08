# Phase 5B — Results Visualization

This document presents the visual experimental results derived from the automated evaluation of the AegisGraph prototype.

## 1. Data Source
All figures and statistics in this document are generated deterministically from `scripts/phase4d_evaluation.json`. This JSON artifact contains the continuous, query-by-query telemetry and retrieval metrics from the Phase 4D automated evaluation harness, running against the `aegisgraph` Neo4j database. 

## 2. Figures Generated

Six core figures were generated and are stored in the `docs/figures/` directory:

1. **Figure 1: EWMA Risk Progression** (`fig1_ewma_risk_progression.png`)
   - *Demonstrates*: How the exponentially weighted moving average (EWMA) risk accumulates over time across different behavioral scenarios. It shows that benign interactions remain safely at LOW risk, while sustained probing gradually builds toward MEDIUM risk.

2. **Figure 2: Security Signal Progression** (`fig2_security_signal_progression.png`)
   - *Demonstrates*: The underlying component signals ($S_{sem}$, $S_{temp}$, $S_{ent}$, $S_{graph}$) driving the instantaneous risk for Scenario H. It visualizes exactly when specific attack vectors (like rapid temporal firing or massive graph footprints) spike during the sequence.

3. **Figure 3: Controlled Data Exposure Comparison** (`fig3_baseline_vs_aegisgraph_exposure.png`)
   - *Demonstrates*: The total absolute number of records passed to the context builder per scenario, comparing the unrestricted static BASELINE against the dynamically restricted AEGISGRAPH model.

4. **Figure 4: Exposure Reduction by Scenario** (`fig4_exposure_reduction.png`)
   - *Demonstrates*: The percentage reduction in exposed records for each scenario. It highlights that benign scenarios (A) experience 0% reduction, preserving utility, while sustained attacks (H) experience severe throttling (41.8%).

5. **Figure 5: Adaptive Policy Behavior** (`fig5_adaptive_policy_behavior.png`)
   - *Demonstrates*: The direct causal relationship between accumulating EWMA risk and the tightening of effective limits ($k_{eff}$ and $d_{eff}$). As the red risk line rises, the context limits (blue) and graph depth limits (green) visibly step down.

6. **Figure 6: Query Blocking Summary by Scenario** (`fig6_query_blocking_summary.png`)
   - *Demonstrates*: The absolute count of queries that were explicitly blocked by the Adaptive Policy because their required graph depth exceeded the currently permitted $d_{eff}$.

## 3. Scenario-Specific Quantitative Results

The following table summarizes the key numerical findings extracted natively from the telemetry (available in `scripts/phase5_results_summary.csv`):

| Scenario | Total Queries | Baseline Exposure | AegisGraph Exposure | Reduction % | Blocked Queries | Final Risk |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| **A_BENIGN_SINGLE_LOOKUP** | 1 | 1 | 1 | 0.00% | 0 | 0.0158 |
| **B_BENIGN_SLOW_EXPLORATION** | 3 | 22 | 21 | 4.55% | 0 | 0.2041 |
| **C_RAPID_REPEATED_PROBING** | 4 | 42 | 40 | 4.76% | 0 | 0.3275 |
| **D_ENTITY_FOCUSED_PROBING** | 5 | 22 | 21 | 4.55% | 0 | 0.2832 |
| **E_PROGRESSIVE_GRAPH_EXPANSION** | 5 | 41 | 40 | 2.44% | 1 | 0.3558 |
| **F_MIXED_MULTI_SIGNAL** | 6 | 42 | 41 | 2.38% | 0 | 0.4457 |
| **G_SUSTAINED_RAPID_ENTITY** | 15 | 91 | 73 | 19.78% | 0 | 0.4369 |
| **H_SUSTAINED_MULTI_VECTOR** | 20 | 189 | 110 | 41.80% | 3 | 0.5176 |

## 4. Important Interpretation Boundaries

To maintain scientific rigor when presenting these results, the following explicit constraints and limitations must be stated:

1. **Controlled Prototype Evaluation**: All results come from controlled, deterministic prototype evaluation sequences (synthetic scenarios), not live stochastic user activity.
2. **Exposure Measurement**: Exposure reduction is measured strictly as the delta in "records passed to the context-building stage" before LLM generation. 
3. **Not a Universal Effectiveness Metric**: Exposure reduction (e.g., the 41.8% in Scenario H) is a scenario-specific outcome demonstrating adaptive throttling. It is **not** equivalent to a universal security effectiveness percentage or general claim of system safety.
4. **No Standard Accuracy Metrics**: The evaluation does not and cannot provide True Positive (TP), False Positive (FP), False Positive Rate (FPR), or True Positive Rate (TPR) metrics because no labeled adversarial ground truth dataset currently exists for these specific behavioral sequences.
5. **Graph Depth Definition**: Graph depth enforcement is implemented as intent-to-depth logical gating at the `RetrievalService` boundary, rather than physical computational measurement of Neo4j Cypher traversals.

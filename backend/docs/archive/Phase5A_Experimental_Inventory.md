# Phase 5A — Experimental Data and Telemetry Inventory

## 1. Existing Experimental Artifacts

An inspection of the repository reveals the following reusable experimental assets:

| Artifact | Type | Purpose | Reusable for Plotting | Limitations |
| :--- | :--- | :--- | :--- | :--- |
| `scripts/evaluate_aegisgraph.py` | Script | End-to-end evaluation harness running 8 scenarios (A-H) comparing BASELINE vs AEGISGRAPH behavior. | N/A | LLM generation is mocked; does not record latency metrics. |
| `scripts/phase4d_evaluation.json` | Data (JSON) | Primary output from the Phase 4D evaluation. Contains query-by-query telemetry and retrieval outcomes for all 8 scenarios. | **Yes** | Does not contain any timing/latency metrics. |
| `scripts/validate_risk_model.py` | Script | Earlier risk model validation script focusing purely on signal scaling. | N/A | Replaced largely by the E2E evaluator. |
| `scripts/validation_results.json` | Data (JSON) | Output from the risk model validation. | **Yes** | Simpler scenarios; lacks policy/exposure metrics. |
| `scripts/extract_metrics.py` | Script | Parses `phase4d_evaluation.json` to calculate aggregate exposure reduction. | N/A | Prints to console; doesn't generate visual plots. |

## 2. Available Metrics

The following metrics are currently captured in `phase4d_evaluation.json`:

### Risk Metrics
- `instantaneous_risk`
- `EWMA_risk`
- Individual signals: `S_sem`, `S_temp`, `S_ent`, `S_graph`
- `risk_level` (LOW, MEDIUM, HIGH)

### Security/Exposure Metrics
- `retrieval_result_count`
- `records_passed_to_context_builder`
- `blocked_by_policy` (boolean)
- Exposure reduction (derived by comparing BASELINE vs AEGISGRAPH records passed)

### Utility Metrics
- Benign queries unmodified (derived from Scenarios A and B where `blocked_by_policy` is false and limits are intact)
- Context availability

### Policy Metrics
- `attenuation_factor`
- `effective_context_limit`
- `effective_graph_depth`

### Timing/Performance Metrics
- **NONE**: The current evaluation harness does not record per-query latency, retrieval latency, security computation latency, or end-to-end latency.

## 3. Possible Results and Visualizations

| Proposed Result / Visualization | Existing Data Available? | Source Artifact | Additional Experiment Needed? |
| :--- | :--- | :--- | :--- |
| 1. EWMA risk progression over sequences | Yes | `phase4d_evaluation.json` | No |
| 2. Individual security signal progression | Yes | `phase4d_evaluation.json` | No |
| 3. Baseline vs AegisGraph exposure comparison | Yes | `phase4d_evaluation.json` | No |
| 4. Exposure reduction by scenario | Yes | `phase4d_evaluation.json` | No |
| 5. Benign utility preservation | Yes | `phase4d_evaluation.json` | No |
| 6. Context limit vs risk | Yes | `phase4d_evaluation.json` | No |
| 7. Graph depth limit vs risk | Yes | `phase4d_evaluation.json` | No |
| 8. Blocked query count by scenario | Yes | `phase4d_evaluation.json` | No |
| 9. Risk level transitions | Yes | `phase4d_evaluation.json` | No |
| 10. Security overhead / latency | **No** | N/A | **Yes** |

## 4. Identified Gaps

### Essential
- **Security Overhead / Latency Measurement**: We must demonstrate that the continuous behavioral telemetry calculation (embedding generation, Neo4j history lookup, metric calculation) does not introduce unacceptable latency to the RAG pipeline.

### Useful but Optional
- **Visualization Scripts**: Python scripts utilizing `matplotlib` or `seaborn` to render the existing JSON data into publication-ready charts (e.g., line charts for EWMA progression, bar charts for exposure reduction).

### Not Worth Doing
- **Real LLM Generation Latency**: Because the prototype relies on external/local LLM APIs (Ollama), generation latency is highly variable and external to our security model's performance. Continuing to mock the LLM for performance tests is appropriate.
- **Stochastic/Adversarial Simulation**: Generating randomized attacks would add significant complexity without necessarily providing clearer evidence than our deterministic Scenarios G and H.

## 5. Recommended Minimal Phase 5 Experiment Plan

To formally conclude the experimental data gathering, we should execute the following minimal plan:

1. **Write Visualization Scripts**: Create a script to parse `phase4d_evaluation.json` and generate the required graphs (Risk Progression, Exposure Reduction, Policy Attenuation).
2. **Instrument Performance Telemetry**: Minorly update `evaluate_aegisgraph.py` (or create a dedicated `evaluate_performance.py`) to measure strictly the execution time of `aegis_security.observe_query` and `aegis_security.calculate_risk`.
3. **Run Overhead Evaluation**: Execute the performance script to capture average security overhead in milliseconds.

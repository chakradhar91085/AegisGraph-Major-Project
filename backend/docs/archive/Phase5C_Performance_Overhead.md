# Phase 5C — Performance and Security Overhead Evaluation

This document outlines the performance characteristics and computational overhead of the AegisGraph security layer, specifically isolating the cost of continuous behavioral telemetry, risk calculation, and adaptive policy enforcement.

## 1. Benchmark Methodology

The benchmark was executed using a standalone harness (`scripts/benchmark_overhead.py`) utilizing Python's high-resolution `time.perf_counter()` to measure precise execution time in milliseconds. 

The evaluation was divided into three measurement phases:
1. **Security Computation Only**: Isolated timing of `observe_query` and `calculate_risk`. This involves fetching semantic embeddings, running Neo4j history lookups, calculating the 4 behavioral signals, updating EWMA, and generating the adaptive policy constraints.
2. **Baseline Retrieval**: Standard Neo4j RAG retrieval without any security layer interception or policy gating.
3. **Protected Retrieval**: The complete AegisGraph pipeline (Security Observation → Policy Enforcement → Retrieval → Security Post-Retrieval Updates).

## 2. Hardware and Environment Description
- **Environment**: Local development environment.
- **Database**: Local Neo4j instance.
- **Embedding Model**: `sentence-transformers/all-MiniLM-L6-v2` executed on local CPU.

*Explicit Constraints:*
> [!WARNING]
> - Results are prototype measurements from the local development environment.
> - They do not represent production throughput.
> - Neo4j/database latency may introduce variance depending on the physical retrieval depth.
> - LLM inference latency (which is generally the slowest component in a RAG pipeline) is explicitly excluded from the primary security-computation overhead measurement.

## 3. Iterations and Configuration

- **Security Computation Iterations**: 100 iterations per sequence.
- **Retrieval Iterations (Baseline vs Protected)**: 50 iterations each.
- The database connection and ML embedding models were actively warmed up before measurements commenced to exclude cold-start initialization latency.

## 4. Measured Results

The primary benchmark results are visualized in `docs/figures/fig7_security_overhead.png` and stored structurally in `scripts/phase5c_performance.json`.

**Key Latency Metrics (Mean per Query):**
- **Security Computation Only**: 12.91 ms
- **Baseline Retrieval**: 8.49 ms
- **Protected Retrieval**: 20.27 ms
- **Empirical Overhead**: 11.78 ms

## 5. Interpretation

The primary result of this benchmark is the incremental computational cost of AegisGraph's behavioral telemetry, risk calculation, and policy evaluation. 

The security layer adds approximately **12.91 milliseconds** of computational overhead per query. In the context of the full retrieval pipeline, the protected retrieval took 20.27 ms compared to the 8.49 ms baseline, representing an absolute empirical overhead of ~11.78 ms (or a ~138.8% relative increase over the extremely fast, bare-metal local retrieval). 

Given that modern end-to-end RAG pipelines typically incur hundreds to thousands of milliseconds of latency due to LLM generation, an incremental 13 ms security penalty is negligible. The security overhead is computationally inexpensive and does not introduce human-perceptible lag into the user experience, validating that continuous behavioral telemetry is viable as an inline security boundary.

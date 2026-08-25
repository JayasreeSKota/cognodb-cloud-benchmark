# Graph Databases Under Pressure: What Happens on 256MB RAM and 0.5 vCPU?

*An empirical performance study comparing CognoDB Cloud, Memgraph, FalkorDB, KùzuDB, and Apache AGE under strict hardware parity.*

---

## Executive Summary

Graph databases are renowned for expressive relationship traversal and rich graph analytics, yet enterprise deployment guides typically prescribe multi-gigabyte or multi-core server footprints. 

*What happens when modern graph database engines are deployed under strict hardware constraints?*

To evaluate real-world performance, memory safety, and stability under low-tier hardware allocations, we evaluated **5 prominent graph database platforms** under identical, strictly audited resource quotas: **0.5 vCPU, 256 MB RAM, and 1 GB disk storage** — matching **CognoDB Cloud's free c0 tier**.

### Evaluated Engines:
1. **CognoDB Cloud** (Managed Cloud Native Graph / Bolt Cypher)
2. **Memgraph v2.18.0** (In-Memory C++ Native Graph)
3. **FalkorDB v4.20.4** (GraphBLAS Sparse Linear Algebra on Redis)
4. **KùzuDB v0.11.3** (Containerized Columnar C++ / Vectorized Execution)
5. **Apache AGE latest** (openCypher Graph Database Extension on PostgreSQL 16)

---

## The Benchmark Arena: Rigorous & Reproducible

```mermaid
graph TD
    A["Stanford SNAP Public Dataset (cit-HepPh 125k Edges)"] --> B["Deterministic CSV Generator (data/raw/)"]
    B --> C["Unified Multi-Run Harness (run_all.py)"]
    C --> D1["Memgraph (Docker 0.5 CPU / 256MB RAM)"]
    C --> D2["FalkorDB (Docker 0.5 CPU / 256MB RAM)"]
    C --> D3["KùzuDB (Docker 0.5 CPU / 256MB RAM)"]
    C --> D4["Apache AGE (Docker 0.5 CPU / 256MB RAM)"]
    C --> D5["CognoDB Cloud (Managed Free c0 Tier)"]
    D1 & D2 & D3 & D4 & D5 --> E["Raw Archive (results/raw/run_01..03/)"]
    E --> F["Statistical Aggregator (results/metrics.json, variance.csv)"]
    F --> G["Automated Charts & Report Sync"]
```

### Key Methodology & Architectural Controls:
- **Public Immutable Dataset**: Stanford SNAP High Energy Physics citation graph (`cit-HepPh`) with **18,317 papers** and **125,000 citation relationships** (Verified SHA-256: `917e77b3344aed33fd2d849443c9512b7c528b9dc87251d4245fb3777bbe4128`).
- **Synthetic Metadata Disclosure**: The graph topology (18,317 papers, 125,000 citation edges) is authentic. Vertex attributes (`category`, `institution`, `year`) and edge `weight` were synthesized deterministically (`random.seed(42)` in `data/download_dataset.py`) to benchmark property filtering and point lookup operations.
- **Strict Cgroup Quotas & Swap Limitations**: Enforced via Docker Compose (`cpus: '0.5'`, `memory: 256M`, `memory-swap: 256M` — setting swap equal to memory, ensuring 0 MB swap headroom / swap disabled).
- **Storage Limitations**: Local container storage is bounded by the host Docker storage driver without XFS project quota enforcement; dataset storage footprint across engines is ~15–45 MB.
- **Query Semantic Parity Suite (`scripts/verify_query_equivalence.py`)**: Verified that point lookups, indexed filters, 1/2/3-hop traversals, count aggregations, and group-by aggregations return 100% logically identical results across all 5 engines.
- **3 Full Repetitions & Statistical Aggregation**: All workloads executed across 3 complete repetitions (`run_01`, `run_02`, `run_03`). Headline numbers report the **median** value across runs, while stability is quantified via **Coefficient of Variation (CV%)** in `results/variance.csv`.
- **Latency Timing & Full Result Materialization**: All timings measure end-to-end execution including complete result iterator consumption (`result.consume()` / full record materialization).
- **Network RTT Isolation**: Client-to-cloud WAN network latency (measured via `scripts/measure_rtt.py`: **50.60 ms median RTT**) is explicitly decoupled from local database processing latencies.

---

## 1. Ingest Throughput

| Platform | Node Ingest (nodes/sec) | Rel Ingest (rels/sec) | Node Time (s) | Rel Time (s) | Total Wall-Clock Time (s) | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **CognoDB Cloud** | 10,629.89 | 9,479.41 | 1.723 s | 13.186 s | 16.598 s | **SUCCESS** |
| **Memgraph** | 41,663.51 | 81,896.88 | 0.440 s | 1.526 s | 2.463 s | **SUCCESS** |
| **FalkorDB** | 140,888.40 | 33,483.08 | 0.130 s | 3.733 s | 3.838 s | **SUCCESS** |
| **KùzuDB** | 3,246.57 | 1,644.04 | 5.642 s | 76.032 s | 81.709 s | **SUCCESS** |
| **Apache AGE** | 92,830.21 | 100,528.71 | 0.197 s | 1.243 s | 1.495 s | **SUCCESS** |

### Architectural Insights:
1. **Apache AGE Relational Heap Batching**: Apache AGE achieved the lowest total wall-clock ingestion time (**1.495 s**), inserting 18,317 nodes at **92,830 nodes/sec** and 125,000 edges at **100,528 rels/sec** directly into PostgreSQL relational heap tables.
2. **Memgraph In-Memory Pointers**: Memgraph achieved **81,896 rels/sec** relationship ingestion throughput, completing the full dataset ingestion in **2.463 seconds** with direct in-memory graph pointer allocation.
3. **FalkorDB GraphBLAS Matrices**: FalkorDB demonstrated the fastest node ingestion (**140,888 nodes/sec**), creating all nodes in **0.130 seconds**. Relationship insertion sustained **33,483 rels/sec** via compressed sparse matrix representations.
4. **CognoDB Cloud Managed Remote Ingestion**: CognoDB Cloud sustained **10,629 nodes/sec** and **9,479 rels/sec** over the network, completing total wall-clock ingest in **16.598 seconds**.
5. **Columnar Disk-Backed Storage (KùzuDB)**: KùzuDB required **81.709 seconds** total wall-clock time under 0.5 vCPU, reflecting disk write transactions and CSR (Compressed Sparse Row) index rebalancing.

---

## 2. Multi-Hop Graph Traversals (Cold vs. Warm)

*Measured across 100 randomized start seeds. Steady-state percentiles ($p50, p95$) reported alongside cold-start first-query latency:*

| Platform | 1-Hop First-Query | 1-Hop $p50$ | 1-Hop $p95$ | 2-Hop First-Query | 2-Hop $p50$ | 2-Hop $p95$ | 3-Hop First-Query | 3-Hop $p50$ | 3-Hop $p95$ |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **CognoDB Cloud** | 45.68 ms | 45.02 ms | 51.10 ms | 46.26 ms | 46.00 ms | 58.70 ms | 43.71 ms | 45.92 ms | 539.51 ms |
| **Memgraph** | 1.96 ms | **0.52 ms** | 0.86 ms | 1.63 ms | **0.51 ms** | 1.09 ms | 0.73 ms | **0.57 ms** | 1.88 ms |
| **FalkorDB** | 13.62 ms | **0.53 ms** | 0.63 ms | 0.55 ms | **0.55 ms** | 0.66 ms | 0.54 ms | **0.53 ms** | 1.40 ms |
| **KùzuDB** | 3.57 ms | 1.52 ms | 1.93 ms | 2.13 ms | 2.01 ms | 2.47 ms | 2.03 ms | 2.12 ms | 4.72 ms |
| **Apache AGE** | 6.15 ms | 5.35 ms | 51.15 ms | 8.12 ms | 6.62 ms | 54.87 ms | 301.04 ms | 216.92 ms | 384.58 ms |

### Architectural Insights:
1. **Local vs. WAN Network Transport**: Memgraph and FalkorDB execute local traversals in **0.51–0.57 ms** ($p50$). CognoDB Cloud executes traversals at **45.02–46.00 ms** ($p50$), aligning with the 50.60 ms client-to-cloud WAN network round-trip time.
2. **GraphBLAS Sparse Vector Multiplication**: FalkorDB's linear algebraic matrix-vector multiplication delivers highly consistent 1-hop ($p50 = 0.53\text{ ms}$), 2-hop ($p50 = 0.55\text{ ms}$), and 3-hop ($p50 = 0.53\text{ ms}$) execution.
3. **Columnar Vectorized Scanning**: KùzuDB sustained **1.52 ms** (1-hop) to **2.12 ms** (3-hop) median latency within its containerized 128 MB buffer pool.
4. **Relational Join Scaling**: Apache AGE handles 1-hop and 2-hop traversals in **5.35 ms** and **6.62 ms**, with 3-hop queries increasing to **216.92 ms** ($p50$) due to recursive relational joins over PostgreSQL edge tables.

---

## 3. Lookups and Aggregations

*All queries measured over 100 iterations after warm-up on indexed properties (`Paper.id` primary, `Paper.category` indexed):*

| Platform | Point $p50$ | Point $p95$ | Indexed $p50$ | Indexed $p95$ | Count Agg $p50$ | Count Agg $p95$ | GroupBy $p50$ | GroupBy $p95$ |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **CognoDB Cloud** | 45.42 ms | 51.54 ms | 56.16 ms | 103.58 ms | 89.78 ms | 100.89 ms | 96.95 ms | 155.36 ms |
| **Memgraph** | **0.48 ms** | 0.70 ms | 1.21 ms | 1.97 ms | 8.56 ms | 52.65 ms | 3.10 ms | 7.11 ms |
| **FalkorDB** | 0.49 ms | **0.59 ms** | **0.56 ms** | **0.66 ms** | **0.75 ms** | **0.85 ms** | **1.96 ms** | **2.73 ms** |
| **KùzuDB** | 1.29 ms | 1.55 ms | 1.73 ms | 1.93 ms | 2.65 ms | 3.35 ms | 2.46 ms | 3.08 ms |
| **Apache AGE** | 2.00 ms | 3.14 ms | 2.88 ms | 5.76 ms | 200.43 ms | 286.99 ms | 8.05 ms | 55.68 ms |

### Architectural Insights:
1. **FalkorDB Linear Algebra Aggregation**: FalkorDB executed global count aggregation in **0.75 ms** ($p50$) and GroupBy aggregations in **1.96 ms** ($p50$), leveraging matrix row/column reduction routines.
2. **Memgraph In-Memory Hash Lookups**: Memgraph executed point lookups in **0.48 ms** ($p50$) and indexed category scans across 3,111 matches in **1.21 ms** ($p50$).
3. **Apache AGE PostgreSQL B-Trees**: Apache AGE executed point lookups in **2.00 ms** ($p50$) and category lookups in **2.88 ms** ($p50$) via PostgreSQL btree functional indexes.
4. **CognoDB Cloud Point & Range Lookups**: Point lookups over WAN returned in **45.42 ms** ($p50$), while multi-record category scans completed in **56.16 ms** ($p50$).

---

## 4. High Concurrency Scaling: Contention on 0.5 vCPU

*80% Read / 20% Write mixed workload evaluated across 1, 10, and 40 concurrent worker clients for 10.0 seconds per level:*

| Platform | Concurrency = 1 QPS | Concurrency = 1 $p95$ | Concurrency = 10 QPS | Concurrency = 10 $p95$ | Concurrency = 40 QPS | Concurrency = 40 $p95$ | Concurrency 40 Errors |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **CognoDB Cloud** | 21.6 QPS | 54.21 ms | 165.6 QPS | 63.95 ms | 202.2 QPS | 358.43 ms | **0** |
| **Memgraph** | **2,016.6 QPS** | **0.56 ms** | **2,743.9 QPS** | **7.58 ms** | **3,131.8 QPS** | **33.08 ms** | **0** |
| **FalkorDB** | 2,024.4 QPS | 0.60 ms | 1,926.7 QPS | 73.26 ms | 1,862.0 QPS | 86.72 ms | **54** |
| **KùzuDB** | 374.9 QPS | 7.05 ms | 534.2 QPS | 22.47 ms | 445.8 QPS | 21.72 ms | **15** |
| **Apache AGE** | 262.5 QPS | 6.99 ms | 244.9 QPS | 117.67 ms | 248.9 QPS | 501.55 ms | **0** |

### Architectural Insights & Error Disclosures:
- **Memgraph Throughput Scaling**: Scaled from **2,016.6 QPS** at 1 client to **3,131.8 QPS** at 40 clients with zero errors under concurrent 20% write contention.
- **CognoDB Cloud Multi-Worker Scaling**: Scaled from **21.6 QPS** at 1 client to **202.2 QPS** at 40 clients with zero transaction errors over the public Internet.
- **Apache AGE Process Isolation**: Maintained a steady **245–262 QPS** with zero errors across all client levels leveraging PostgreSQL MVCC.
- **FalkorDB Concurrency Contention (54 Errors)**: Under 40 concurrent workers on 0.5 vCPU with 20% write transactions, FalkorDB recorded **54 write retry / transaction conflict errors** due to Redis single-threaded command serialization and transaction rollbacks during high write pressure.
- **KùzuDB Buffer Lock Contention (15 Errors)**: Under 40 concurrent workers, KùzuDB recorded **15 write lock conflict errors** due to table-level write lock serialization within the 128 MB buffer pool container.

---

## 5. Repetition Stability & Variance Analysis

*Across 3 complete repetitions with full database rebuild between runs (from `results/variance.csv`):*

| Database | Key Metric | Run 1 | Run 2 | Run 3 | Median (Headline) | CV (%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **CognoDB Cloud** | Ingest Total Wall Clock (s) | 16.598 s | 16.524 s | 16.609 s | **16.598 s** | 0.23% |
| **CognoDB Cloud** | 1-Hop p50 (ms) | 45.02 ms | 45.459 ms | 44.817 ms | **45.02 ms** | 0.59% |
| **CognoDB Cloud** | 2-Hop p50 (ms) | 46.158 ms | 46.003 ms | 45.468 ms | **46.003 ms** | 0.64% |
| **CognoDB Cloud** | 3-Hop p50 (ms) | 46.092 ms | 45.924 ms | 45.347 ms | **45.924 ms** | 0.70% |
| **CognoDB Cloud** | Point Lookup p50 (ms) | 45.313 ms | 45.564 ms | 45.416 ms | **45.416 ms** | 0.23% |
| **CognoDB Cloud** | Concurrency 10 QPS | 168.83 | 165.20 | 165.57 | **165.57** | 0.98% |
| **Memgraph** | Ingest Total Wall Clock (s) | 2.219 s | 2.639 s | 2.463 s | **2.463 s** | 7.06% |
| **Memgraph** | 1-Hop p50 (ms) | 0.517 ms | 0.719 ms | 0.491 ms | **0.517 ms** | 17.70% |
| **Memgraph** | Point Lookup p50 (ms) | 0.482 ms | 0.603 ms | 0.474 ms | **0.482 ms** | 11.36% |
| **Memgraph** | Concurrency 10 QPS | 2,740.70 | 2,743.88 | 3,151.04 | **2,743.88** | 6.69% |
| **FalkorDB** | Ingest Total Wall Clock (s) | 3.838 s | 3.816 s | 3.947 s | **3.838 s** | 1.74% |
| **FalkorDB** | 1-Hop p50 (ms) | 0.485 ms | 0.532 ms | 0.536 ms | **0.532 ms** | 4.47% |
| **FalkorDB** | Point Lookup p50 (ms) | 0.458 ms | 0.500 ms | 0.494 ms | **0.494 ms** | 3.83% |
| **FalkorDB** | Concurrency 10 QPS | 1,926.67 | 1,705.10 | 2,123.99 | **1,926.67** | 8.92% |
| **KùzuDB** | Ingest Total Wall Clock (s) | 81.709 s | 79.450 s | 83.210 s | **81.709 s** | 1.88% |
| **KùzuDB** | 1-Hop p50 (ms) | 2.085 ms | 1.522 ms | 1.435 ms | **1.522 ms** | 17.14% |
| **KùzuDB** | Point Lookup p50 (ms) | 1.294 ms | 1.391 ms | 1.203 ms | **1.294 ms** | 5.92% |
| **KùzuDB** | Concurrency 10 QPS | 516.71 | 534.25 | 551.02 | **534.25** | 2.62% |
| **Apache AGE** | Ingest Total Wall Clock (s) | 1.495 s | 1.414 s | 1.540 s | **1.495 s** | 3.52% |
| **Apache AGE** | 1-Hop p50 (ms) | 5.353 ms | 5.404 ms | 5.130 ms | **5.353 ms** | 2.25% |
| **Apache AGE** | 2-Hop p50 (ms) | 6.532 ms | 8.273 ms | 6.619 ms | **6.619 ms** | 11.22% |
| **Apache AGE** | 3-Hop p50 (ms) | 284.922 ms | 4.173 ms | 216.923 ms | **216.923 ms** | 70.90% |
| **Apache AGE** | Point Lookup p50 (ms) | 2.448 ms | 1.998 ms | 1.744 ms | **1.998 ms** | 14.11% |
| **Apache AGE** | Concurrency 10 QPS | 244.94 | 230.23 | 267.21 | **244.94** | 6.14% |

*Statistical Assessment*: CognoDB Cloud demonstrated exceptional stability ($CV < 1\%$ across all multi-hop traversals and point lookups). Local competitor engines exhibited low-to-moderate variance ($CV \approx 2\text{--}17\%$) primarily driven by sub-millisecond OS scheduling jitter on 0.5 vCPU, while Apache AGE showed higher variance on 3-hop recursive relational joins ($CV = 70.9\%$) depending on PostgreSQL join plan selection across cold/warm runs.

---

## 6. Client-to-Cloud Network RTT Breakdown

To prevent conflating cloud network transit with database engine execution, network round-trip time was sampled against the cloud database host (`results/rtt_measurements.json`):

| Network Statistic | Latency |
| :--- | :--- |
| **Minimum RTT** | 46.21 ms |
| **Median RTT** | 50.60 ms |
| **Mean RTT** | 53.73 ms |
| **p95 RTT** | 60.30 ms |
| **Maximum RTT** | 128.90 ms |
| **Standard Deviation** | 14.38 ms |

> [!NOTE]
> Local engines execute queries over loopback IPC ($< 1\text{ ms}$), whereas managed cloud databases over WAN inherently incur TCP/TLS and geographic routing round-trip latency ($\sim 46\text{--}60\text{ ms}$).

---

## 7. Resource Footprint & 256MB Cgroup Audit

| Platform | Memory Limit | Steady-State RAM | Footprint Ratio | Status Under 256MB Cgroup |
| :--- | :--- | :--- | :--- | :--- |
| **CognoDB Cloud** | Managed | Cloud Tier | Cloud | **MANAGED** (Zero Local Footprint) |
| **Memgraph** | 256 MB | 86.1 MB | 33.6% | **STABLE** (Fastest Traversal & Highest QPS) |
| **FalkorDB** | 256 MB | 46.2 MB | 18.0% | **STABLE** (Lowest Memory Footprint) |
| **KùzuDB** | 256 MB | 68.6 MB | 26.8% | **STABLE** (Predictable Columnar Buffers) |
| **Apache AGE** | 256 MB | 35.4 MB | 13.8% | **STABLE** (Fastest Ingest & Minimal Footprint) |

---

## Engine Selection Guide

| Use Case | Recommended Platform | Primary Benefit |
| :--- | :--- | :--- |
| **High-Throughput In-Memory Graph** | **Memgraph** | Fast ingest (>81k rels/s), sub-millisecond graph traversals, and highest QPS under concurrency (3,131 QPS with 0 errors). |
| **Compact Memory & Redis Ecosystem** | **FalkorDB** | Minimal footprint (46.2 MB) with fast matrix-based graph aggregations. |
| **PostgreSQL & Hybrid Relational/Graph** | **Apache AGE** | Lowest memory footprint (35.4 MB), fastest ingest (1.495 s), and native openCypher on PostgreSQL. |
| **Embedded Vectorized Analytics** | **KùzuDB** | Robust columnar execution with fixed buffer pool management. |
| **Managed Cloud Graph API** | **CognoDB Cloud** | Instant Bolt protocol access with zero local memory or infrastructure overhead. |

---

*All dataset scripts, Docker configurations, raw run logs, and verification harnesses are available in the repository for one-command reproduction via `make benchmark` or `./scripts/run_benchmark.sh`.*

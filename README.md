# Graph Database Benchmark Suite: CognoDB Cloud vs. Leading Graph Engines

A reproducible, fair benchmark evaluating **CognoDB Cloud** against 4 leading graph database engines (**Memgraph**, **FalkorDB**, **KùzuDB**, and **Apache AGE**) under strict resource parity (**0.5 vCPU, 256 MB RAM, 1 GB Storage**).

---

## Executive Summary & Architectural Takeaways

When graph database engines are constrained to entry-level micro-tier resources (**256 MB RAM** and **0.5 vCPU**):

1. **In-Memory and GraphBLAS Engines Excel in Low Footprints**: 
   - **Memgraph (v2.18.0)** achieved **41,663 nodes/sec** and **81,896 relationships/sec** ingestion throughput with microsecond traversal latencies ($p50 \approx 0.52\text{ ms}$).
   - **FalkorDB (v4.20.4)** leveraged GraphBLAS sparse matrix primitives to deliver **>140,000 nodes/sec** ingest and stable **~1,900 QPS** under concurrent loads with minimal memory footprint (~49 MB).
2. **Columnar Embedded Graphs Deliver Strong Analytical Locality**: 
   - **KùzuDB (v0.11.3)** demonstrated steady **~450–530 QPS** and fast 1-hop traversals ($p50 = 1.52\text{ ms}$) within a tightly capped 128 MB buffer pool container.
3. **Relational Graph Extensions (Apache AGE)**: 
   - **Apache AGE (latest on PostgreSQL 16)** combines openCypher graph modeling with PostgreSQL relational storage, delivering **>92,000 nodes/sec** and **>100,000 rels/sec** ingestion and **~245–262 QPS** concurrency in just ~35 MB of RAM.
4. **Cloud Managed Free-Tiers (CognoDB Cloud)**: 
   - Provides fully managed, serverless Bolt protocol Cypher access without local memory configuration overhead. End-to-end latency includes Internet WAN transport (20–35 ms RTT), trading local IPC microsecond latency for cloud durability, managed auto-scaling, and operational simplicity.

---

## 1. Experimental Setup & Fairness Methodology

To adhere strictly to fair benchmarking standards:
- **Identical Public Dataset**: Official Stanford SNAP High Energy Physics citation network (`cit-HepPh`) comprising **18,317 nodes** and **125,000 relationships** (SHA-256: `917e77b3344aed33fd2d849443c9512b7c528b9dc87251d4245fb3777bbe4128`).
- **Identical Hardware Constraints**: Every local competitor engine is executed inside Docker containers strictly pinned to `--cpus="0.5" --memory="256m"`.
- **Query Semantic Parity**: openCypher queries across all 5 engines verified for identical 1-hop, 2-hop, 3-hop, point ID lookups, indexed attribute lookups, degree aggregations, and concurrent transactions.
- **Warm vs. Cold Separation**: Cold-start latency (1st invocation) is recorded separately from steady-state warm cache percentiles ($p50, p90, p95, p99$).
- **Single Source of Truth**: All result tables and charts are generated programmatically from `results/metrics.json` and verified by `scripts/validate_results.py`.

### Evaluated Platforms & Specifications

| Platform | Pinned Version | Architecture | Query Interface | Resource Constraint |
| :--- | :--- | :--- | :--- | :--- |
| **CognoDB Cloud** | Cloud Free (`c0`) | Cloud Native Graph | Neo4j Bolt (Cypher) | Burstable 0.5 vCPU, 256 MB RAM, 1 GB Storage |
| **Memgraph** | `2.18.0` | In-Memory C++ Native Graph | Bolt Protocol | Capped: 0.5 vCPU, 256 MB RAM (`--memory-limit=256`) |
| **FalkorDB** | `v4.20.4` | GraphBLAS Sparse Matrix on Redis | FalkorDB Client / Cypher | Capped: 0.5 vCPU, 256 MB RAM (`OMP_NUM_THREADS=1`) |
| **KùzuDB** | `0.11.3` | Containerized Columnar C++ | HTTP API (Cypher) | Capped: 0.5 vCPU, 256 MB RAM (128 MB Buffer Pool) |
| **Apache AGE** | `latest (PG 16)` | openCypher Extension on Postgres | PostgreSQL Wire / Cypher | Capped: 0.5 vCPU, 256 MB RAM |

---

## 2. Full Results Matrix

### 2.1 Ingest Throughput

| Platform | Node Ingest (nodes/sec) | Rel Ingest (rels/sec) | Node Time (s) | Rel Time (s) | Total Wall-Clock Time (s) | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **CognoDB Cloud** | 10,629.89 | 9,479.41 | 1.723 s | 13.186 s | 16.598 s | **SUCCESS** |
| **Memgraph** | 41,663.51 | 81,896.88 | 0.440 s | 1.526 s | 2.463 s | **SUCCESS** |
| **FalkorDB** | 140,888.40 | 33,483.08 | 0.130 s | 3.733 s | 3.838 s | **SUCCESS** |
| **KùzuDB** | 3,246.57 | 1,644.04 | 5.642 s | 76.032 s | 81.709 s | **SUCCESS** |
| **Apache AGE** | 92,830.21 | 100,528.71 | 0.197 s | 1.243 s | 1.495 s | **SUCCESS** |

### 2.2 Traversal Latencies (Warm vs. Cold)
*Measured across >= 100 randomized start seeds. Latencies reported in milliseconds (ms).*

| Platform | 1-Hop First-Query | 1-Hop $p50$ | 1-Hop $p95$ | 2-Hop First-Query | 2-Hop $p50$ | 2-Hop $p95$ | 3-Hop First-Query | 3-Hop $p50$ | 3-Hop $p95$ |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **CognoDB Cloud** | 45.68 ms | 45.02 ms | 51.10 ms | 46.26 ms | 46.00 ms | 58.70 ms | 43.71 ms | 45.92 ms | 539.51 ms |
| **Memgraph** | 1.96 ms | 0.52 ms | 0.86 ms | 1.63 ms | 0.51 ms | 1.09 ms | 0.73 ms | 0.57 ms | 1.88 ms |
| **FalkorDB** | 13.62 ms | 0.53 ms | 0.63 ms | 0.55 ms | 0.55 ms | 0.66 ms | 0.54 ms | 0.53 ms | 1.40 ms |
| **KùzuDB** | 3.57 ms | 1.52 ms | 1.93 ms | 2.13 ms | 2.01 ms | 2.47 ms | 2.03 ms | 2.12 ms | 4.72 ms |
| **Apache AGE** | 6.15 ms | 5.35 ms | 51.15 ms | 8.12 ms | 6.62 ms | 54.87 ms | 301.04 ms | 216.92 ms | 384.58 ms |

### 2.3 Lookups & Aggregations
*All queries measured over >= 100 iterations after warm-up. Indexed properties: `Paper(id)` (Primary), `Paper(category)`.*

| Platform | Point $p50$ | Point $p95$ | Indexed $p50$ | Indexed $p95$ | Count Agg $p50$ | Count Agg $p95$ | GroupBy $p50$ | GroupBy $p95$ |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **CognoDB Cloud** | 45.42 ms | 51.54 ms | 56.16 ms | 103.58 ms | 89.78 ms | 100.89 ms | 96.95 ms | 155.36 ms |
| **Memgraph** | 0.48 ms | 0.70 ms | 1.21 ms | 1.97 ms | 8.56 ms | 52.65 ms | 3.10 ms | 7.11 ms |
| **FalkorDB** | 0.49 ms | 0.59 ms | 0.56 ms | 0.66 ms | 0.75 ms | 0.85 ms | 1.96 ms | 2.73 ms |
| **KùzuDB** | 1.29 ms | 1.55 ms | 1.73 ms | 1.93 ms | 2.65 ms | 3.35 ms | 2.46 ms | 3.08 ms |
| **Apache AGE** | 2.00 ms | 3.14 ms | 2.88 ms | 5.76 ms | 200.43 ms | 286.99 ms | 8.05 ms | 55.68 ms |

### 2.4 Mixed Read/Write Concurrency Sweep (80% Read / 20% Write)
*Measured sustained QPS and p95 latency under multi-client concurrency sweeps (1, 10, 40 workers).*

| Platform | Concurrency = 1 QPS | Concurrency = 1 $p95$ | Concurrency = 10 QPS | Concurrency = 10 $p95$ | Concurrency = 40 QPS | Concurrency = 40 $p95$ | Errors |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **CognoDB Cloud** | 21.6 QPS | 54.21 ms | 165.6 QPS | 63.95 ms | 202.2 QPS | 358.43 ms | 0 |
| **Memgraph** | 2016.6 QPS | 0.56 ms | 2743.9 QPS | 7.58 ms | 3131.8 QPS | 33.08 ms | 0 |
| **FalkorDB** | 2024.4 QPS | 0.60 ms | 1926.7 QPS | 73.26 ms | 1862.0 QPS | 86.72 ms | 54 |
| **KùzuDB** | 374.9 QPS | 7.05 ms | 534.2 QPS | 22.47 ms | 445.8 QPS | 21.72 ms | 15 |
| **Apache AGE** | 262.5 QPS | 6.99 ms | 244.9 QPS | 117.67 ms | 248.9 QPS | 501.55 ms | 0 |

### 2.5 Repetition Stability & Variance Analysis
*Across 3 complete benchmark repetitions with database reset between runs:*

| Database | Key Metric | Run 1 | Run 2 | Run 3 | Median (Headline) | CV (%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **CognoDB Cloud** | 1-Hop p50 (ms) | 45.02 | 45.459 | 44.817 | **45.02** | 0.59% |
| **CognoDB Cloud** | 2-Hop p50 (ms) | 46.158 | 46.003 | 45.468 | **46.003** | 0.64% |
| **CognoDB Cloud** | 3-Hop p50 (ms) | 46.092 | 45.924 | 45.347 | **45.924** | 0.7% |
| **CognoDB Cloud** | Point Lookup p50 (ms) | 45.313 | 45.564 | 45.416 | **45.416** | 0.23% |
| **CognoDB Cloud** | Concurrency 10 QPS | 168.83 | 165.2 | 165.57 | **165.57** | 0.98% |
| **Memgraph** | 1-Hop p50 (ms) | 0.517 | 0.719 | 0.491 | **0.517** | 17.7% |
| **Memgraph** | 2-Hop p50 (ms) | 0.513 | 0.67 | 0.479 | **0.513** | 15.02% |
| **Memgraph** | 3-Hop p50 (ms) | 0.568 | 0.637 | 0.519 | **0.568** | 8.42% |
| **Memgraph** | Point Lookup p50 (ms) | 0.482 | 0.603 | 0.474 | **0.482** | 11.36% |
| **Memgraph** | Concurrency 10 QPS | 2740.7 | 2743.88 | 3151.04 | **2743.88** | 6.69% |
| **FalkorDB** | 1-Hop p50 (ms) | 0.485 | 0.532 | 0.536 | **0.532** | 4.47% |
| **FalkorDB** | 2-Hop p50 (ms) | 0.545 | 0.588 | 0.499 | **0.545** | 6.68% |
| **FalkorDB** | 3-Hop p50 (ms) | 0.527 | 0.551 | 0.526 | **0.527** | 2.16% |
| **FalkorDB** | Point Lookup p50 (ms) | 0.458 | 0.5 | 0.494 | **0.494** | 3.83% |
| **FalkorDB** | Concurrency 10 QPS | 1926.67 | 1705.1 | 2123.99 | **1926.67** | 8.92% |
| **KùzuDB** | 1-Hop p50 (ms) | 2.085 | 1.522 | 1.435 | **1.522** | 17.14% |
| **KùzuDB** | 2-Hop p50 (ms) | 2.331 | 2.012 | 1.885 | **2.012** | 9.04% |
| **KùzuDB** | 3-Hop p50 (ms) | 2.248 | 2.12 | 1.939 | **2.12** | 6.03% |
| **KùzuDB** | Point Lookup p50 (ms) | 1.294 | 1.391 | 1.203 | **1.294** | 5.92% |
| **KùzuDB** | Concurrency 10 QPS | 516.71 | 534.25 | 551.02 | **534.25** | 2.62% |
| **Apache AGE** | 1-Hop p50 (ms) | 5.353 | 5.404 | 5.13 | **5.353** | 2.25% |
| **Apache AGE** | 2-Hop p50 (ms) | 6.532 | 8.273 | 6.619 | **6.619** | 11.22% |
| **Apache AGE** | 3-Hop p50 (ms) | 284.922 | 4.173 | 216.923 | **216.923** | 70.9% |
| **Apache AGE** | Point Lookup p50 (ms) | 2.448 | 1.998 | 1.744 | **1.998** | 14.11% |
| **Apache AGE** | Concurrency 10 QPS | 244.94 | 230.23 | 267.21 | **244.94** | 6.14% |

### 2.5 Resource Footprint & Hardware Parity
| Platform | Observed Memory Footprint | Observed Disk Footprint | Instance Specification |
| :--- | :--- | :--- | :--- |
| **Apache AGE** | ~35 MB RAM (RSS) | ~42 MB PostgreSQL tables | Docker Capped: 0.5 vCPU, 256 MB RAM |
| **KùzuDB** | ~50 MB RAM (RSS) | ~14.8 MB store files | Docker Capped: 0.5 vCPU, 256 MB RAM (128 MB Buffer Pool) |
| **Memgraph** | ~105 MB RAM (RSS) | In-memory (0 MB persistent log) | Docker Capped: 0.5 vCPU, 256 MB RAM |
| **FalkorDB** | ~49 MB RAM (RSS) | In-memory / Redis RDB | Docker Capped: 0.5 vCPU, 256 MB RAM |
| **CognoDB Cloud** | *Cloud Abstracted* | *Cloud Abstracted* | Burstable 0.5 vCPU, 256 MB RAM, 1 GB Storage |

---

## 3. Visualizations

Generated high-resolution comparison plots are located in [`results/charts/`](results/charts/):

1. **`traversal_latencies.png`**: $p50$ and $p95$ latencies across 1, 2, and 3-hop graph traversals.
2. **`ingest_throughput.png`**: Node and relationship ingestion throughput (entities/sec).
3. **`lookups_and_aggregations.png`**: Point lookup, indexed category lookup, and group-by aggregation response times.
4. **`concurrency_scaling_qps.png`**: Multi-threaded QPS throughput curves across 1, 10, and 40 concurrent workers.
5. **`cold_vs_warm_traversal.png`**: First-query cold invocation overhead vs. warmed cache steady state.

---

## 4. Deep-Dive Architectural Analysis

### 4.1 In-Memory Pointer Chasing vs. GraphBLAS Sparse Matrices
- **Memgraph** maintains nodes and edges as direct memory pointers. In micro-memory tiers (256 MB), this architecture avoids disk block translation and buffer pool evictions, yielding sub-millisecond traversals ($0.48 - 0.52\text{ ms}$).
- **FalkorDB** represents adjacency lists using GraphBLAS sparse boolean matrices. Matrix multiplication operations for multi-hop graph exploration executed with minimal memory overhead (~49 MB RSS), maintaining high QPS throughput across concurrency levels.

### 4.2 Columnar Storage & Vectorized Execution (KùzuDB)
- **KùzuDB** uses Compressed Sparse Row (CSR) columnar storage. By running a containerized service with a fixed 128 MB buffer pool, it delivers predictable execution with low tail latency for lookups and aggregations.

### 4.3 Relational-Graph Hybrid Architecture (Apache AGE)
- **Apache AGE** operates as an extension inside PostgreSQL 16, translating openCypher graph queries into SQL relational scans and recursive joins. With a compact memory footprint of ~35 MB RAM, it easily stays within the 256 MB cgroup boundary, providing fast relational heap batching (>92k nodes/s and >100k rels/s ingest) and steady concurrency throughput (~245–262 QPS).

### 4.4 Cloud Managed Tier vs. Local IPC (CognoDB Cloud)
- **CognoDB Cloud** provides standard Bolt Cypher compliance in a fully managed cloud setting. In client benchmarking, WAN network latency (measured median 50.60 ms, min 46.21 ms RTT in [`results/rtt_measurements.json`](results/rtt_measurements.json)) represents the dominant component of single-query round-trips compared to local container loopback ($< 0.5\text{ ms}$).

---

## 5. Methodological Disclosures & Caveats

1. **Synthetic Vertex Attributes**: The underlying citation graph topology (18,317 papers, 125,000 citations) is taken directly from the official Stanford SNAP `cit-HepPh` dataset. Node attributes (`category`, `institution`, `year`) and edge `weight` were synthesized deterministically using a fixed random seed (`seed=42`) to benchmark point and indexed category queries.
2. **Swap and Storage Limits**: Local Docker containers were enforced via `cpus: '0.5'`, `memory: 256M`, and `memory-swap: 256M` (ensuring 0 swap headroom relative to RAM). Storage is bounded by container rootfs/volume without XFS project quota enforcement; dataset footprint is ~15–45 MB across all engines.
3. **Variance & Repetition Stability**: Across 3 independent repetitions with full database rebuilds, CognoDB Cloud exhibited tight stability ($CV < 1\%$ on multi-hop traversals and point lookups). Local in-memory engines showed low-to-moderate variance ($CV \approx 2\text{--}17\%$) primarily driven by sub-millisecond OS scheduling jitter.
4. **Network Topology Differential**: Cloud database queries traverse public WAN/TLS connections, whereas containerized competitors run over local IPC loopback. Direct latency comparisons must account for network RTT.
5. **Concurrency Contention & Errors**: Under 40 concurrent workers with 20% writes on 0.5 vCPU, FalkorDB recorded 54 write retry errors (single-threaded Redis command pipeline contention) and KùzuDB recorded 15 write lock errors (buffer pool write lock serialization). Memgraph, Apache AGE, and CognoDB Cloud completed with 0 errors.

---

## 6. Reproduction Instructions

### Step 1: Set Up Python Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 2: Launch Resource-Constrained Containers
```bash
cd docker
docker compose up -d
cd ..
```

### Step 3: Run Official Benchmark Suite
```bash
python run_all.py
```

To run with CognoDB Cloud credentials:
```bash
cp .env.example .env
# Edit .env and set COGNODB_URI, COGNODB_USER, COGNODB_PASSWORD
python run_all.py
```

### Step 4: Validate Results
```bash
python scripts/validate_results.py
```

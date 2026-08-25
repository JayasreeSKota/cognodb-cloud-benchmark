"""
Traversal workload runner (1-hop, 2-hop, 3-hop).
Measures: Cold-start latency (1st invocation), p50, p90, p95, p99, mean, stddev from >= 100 random starting nodes.
"""

import time
import random
from typing import List, Tuple
from ..harness.base import BaseGraphAdapter
from ..harness.stats import LatencyDistribution, compute_percentiles

def run_traversals_benchmark(
    adapter: BaseGraphAdapter,
    node_ids: List[int],
    warmup_iterations: int = 15,
    measured_iterations: int = 100,
    seed: int = 42
) -> Tuple[LatencyDistribution, LatencyDistribution, LatencyDistribution]:
    print(f"\n--- Running Traversal Workloads on [{adapter.name}] ---")
    random.seed(seed)
    
    total_needed = warmup_iterations + measured_iterations
    sample_nodes = random.choices(node_ids, k=total_needed)
    warmup_seeds = sample_nodes[:warmup_iterations]
    test_seeds = sample_nodes[warmup_iterations:]

    def measure_hops(hop_func, hop_name: str) -> LatencyDistribution:
        # Measure cold start (exact first invocation)
        first_seed = warmup_seeds[0]
        t0 = time.perf_counter()
        _ = hop_func(first_seed)
        cold_latency_ms = (time.perf_counter() - t0) * 1000.0

        # Complete warm-up
        for s in warmup_seeds[1:]:
            try:
                _ = hop_func(s)
            except Exception:
                pass

        # Measured steady-state warm iterations
        latencies = []
        for s in test_seeds:
            t_start = time.perf_counter()
            try:
                _ = hop_func(s)
            except Exception:
                pass
            lat_ms = (time.perf_counter() - t_start) * 1000.0
            latencies.append(lat_ms)

        dist = compute_percentiles(latencies, cold_latency_ms=cold_latency_ms)
        print(f"[{adapter.name}] {hop_name} (N={len(latencies)}): Cold={dist.cold_latency_ms:.2f}ms | p50={dist.p50_ms:.2f}ms | p90={dist.p90_ms:.2f}ms | p95={dist.p95_ms:.2f}ms | p99={dist.p99_ms:.2f}ms")
        return dist

    d1 = measure_hops(adapter.run_traversal_1hop, "1-Hop Traversal")
    d2 = measure_hops(adapter.run_traversal_2hop, "2-Hop Traversal")
    d3 = measure_hops(adapter.run_traversal_3hop, "3-Hop Traversal")

    return d1, d2, d3

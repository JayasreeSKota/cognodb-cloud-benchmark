"""
Lookups workload runner (Point ID lookups & Indexed category lookups).
Measures: Cold start, p50, p90, p95, p99, mean, and stddev latencies over >= 100 iterations.
"""

import time
import random
from typing import List, Tuple
from ..harness.base import BaseGraphAdapter
from ..harness.stats import LatencyDistribution, compute_percentiles

def run_lookups_benchmark(
    adapter: BaseGraphAdapter,
    node_ids: List[int],
    categories: List[str],
    warmup_iterations: int = 15,
    measured_iterations: int = 100,
    seed: int = 42
) -> Tuple[LatencyDistribution, LatencyDistribution]:
    print(f"\n--- Running Lookup Workloads on [{adapter.name}] ---")
    random.seed(seed)
    
    # 1. Point lookups by ID
    point_seeds = random.choices(node_ids, k=warmup_iterations + measured_iterations)
    
    # Cold start point lookup
    t0 = time.perf_counter()
    _ = adapter.run_point_lookup(point_seeds[0])
    cold_point = (time.perf_counter() - t0) * 1000.0
    
    for s in point_seeds[1:warmup_iterations]:
        try:
            adapter.run_point_lookup(s)
        except Exception:
            pass
        
    point_lats = []
    for s in point_seeds[warmup_iterations:]:
        t_start = time.perf_counter()
        try:
            _ = adapter.run_point_lookup(s)
        except Exception:
            pass
        point_lats.append((time.perf_counter() - t_start) * 1000.0)
        
    point_dist = compute_percentiles(point_lats, cold_latency_ms=cold_point)
    print(f"[{adapter.name}] Point Lookup (N={len(point_lats)}): Cold={point_dist.cold_latency_ms:.2f}ms | p50={point_dist.p50_ms:.2f}ms | p90={point_dist.p90_ms:.2f}ms | p95={point_dist.p95_ms:.2f}ms | p99={point_dist.p99_ms:.2f}ms")

    # 2. Indexed lookups by Category
    cat_seeds = random.choices(categories, k=warmup_iterations + measured_iterations)
    t0 = time.perf_counter()
    _ = adapter.run_indexed_lookup(cat_seeds[0])
    cold_indexed = (time.perf_counter() - t0) * 1000.0
    
    for c in cat_seeds[1:warmup_iterations]:
        try:
            adapter.run_indexed_lookup(c)
        except Exception:
            pass
        
    indexed_lats = []
    for c in cat_seeds[warmup_iterations:]:
        t_start = time.perf_counter()
        try:
            _ = adapter.run_indexed_lookup(c)
        except Exception:
            pass
        indexed_lats.append((time.perf_counter() - t_start) * 1000.0)
        
    indexed_dist = compute_percentiles(indexed_lats, cold_latency_ms=cold_indexed)
    print(f"[{adapter.name}] Indexed Lookup (N={len(indexed_lats)}): Cold={indexed_dist.cold_latency_ms:.2f}ms | p50={indexed_dist.p50_ms:.2f}ms | p90={indexed_dist.p90_ms:.2f}ms | p95={indexed_dist.p95_ms:.2f}ms | p99={indexed_dist.p99_ms:.2f}ms")

    return point_dist, indexed_dist

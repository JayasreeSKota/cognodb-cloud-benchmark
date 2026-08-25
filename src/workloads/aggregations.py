"""
Aggregations workload runner (Global counts & Group-by style aggregations).
Measures: Cold start, p50, p90, p95, p99, mean, and stddev latencies over >= 100 iterations.
"""

import time
from typing import Tuple
from ..harness.base import BaseGraphAdapter
from ..harness.stats import LatencyDistribution, compute_percentiles

def run_aggregations_benchmark(
    adapter: BaseGraphAdapter,
    warmup_iterations: int = 10,
    measured_iterations: int = 100
) -> Tuple[LatencyDistribution, LatencyDistribution]:
    print(f"\n--- Running Aggregation Workloads on [{adapter.name}] ---")
    
    # 1. Global count
    t0 = time.perf_counter()
    _ = adapter.run_aggregation_count()
    cold_count = (time.perf_counter() - t0) * 1000.0
    
    for _ in range(warmup_iterations - 1):
        try:
            _ = adapter.run_aggregation_count()
        except Exception:
            pass
        
    count_lats = []
    for _ in range(measured_iterations):
        t_start = time.perf_counter()
        try:
            _ = adapter.run_aggregation_count()
        except Exception:
            pass
        count_lats.append((time.perf_counter() - t_start) * 1000.0)
        
    count_dist = compute_percentiles(count_lats, cold_latency_ms=cold_count)
    print(f"[{adapter.name}] Count Aggregation (N={len(count_lats)}): Cold={count_dist.cold_latency_ms:.2f}ms | p50={count_dist.p50_ms:.2f}ms | p90={count_dist.p90_ms:.2f}ms | p95={count_dist.p95_ms:.2f}ms | p99={count_dist.p99_ms:.2f}ms")

    # 2. Group-by category aggregation
    t0 = time.perf_counter()
    _ = adapter.run_aggregation_group_by()
    cold_groupby = (time.perf_counter() - t0) * 1000.0
    
    for _ in range(warmup_iterations - 1):
        try:
            _ = adapter.run_aggregation_group_by()
        except Exception:
            pass
        
    groupby_lats = []
    for _ in range(measured_iterations):
        t_start = time.perf_counter()
        try:
            _ = adapter.run_aggregation_group_by()
        except Exception:
            pass
        groupby_lats.append((time.perf_counter() - t_start) * 1000.0)
        
    groupby_dist = compute_percentiles(groupby_lats, cold_latency_ms=cold_groupby)
    print(f"[{adapter.name}] GroupBy Aggregation (N={len(groupby_lats)}): Cold={groupby_dist.cold_latency_ms:.2f}ms | p50={groupby_dist.p50_ms:.2f}ms | p90={groupby_dist.p90_ms:.2f}ms | p95={groupby_dist.p95_ms:.2f}ms | p99={groupby_dist.p99_ms:.2f}ms")

    return count_dist, groupby_dist

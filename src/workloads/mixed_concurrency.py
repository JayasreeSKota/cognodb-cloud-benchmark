"""
Mixed Concurrency Workload runner.
Sweeps client concurrency levels (1, 10, 40 workers) with an 80% read / 20% write workload.
Measures: Sustained Queries Per Second (QPS), p50, p90, p95, p99 latencies, and error rates under contention.
"""

import time
import random
import concurrent.futures
from typing import List, Tuple, Dict
import numpy as np
from ..harness.base import BaseGraphAdapter
from ..harness.stats import ConcurrencyMetrics

def run_single_client_worker(
    adapter: BaseGraphAdapter,
    node_ids: List[int],
    duration_sec: float,
    read_ratio: float = 0.8
) -> Tuple[List[float], int]:
    latencies = []
    errors = 0
    end_time = time.perf_counter() + duration_sec
    
    while time.perf_counter() < end_time:
        is_read = random.random() < read_ratio
        t_start = time.perf_counter()
        try:
            if is_read:
                # 50% 1-hop traversal, 50% point lookup
                node_id = random.choice(node_ids)
                if random.random() < 0.5:
                    adapter.run_traversal_1hop(node_id)
                else:
                    adapter.run_point_lookup(node_id)
            else:
                # Write operation: insert citation link
                src = random.choice(node_ids)
                dst = random.choice(node_ids)
                adapter.run_write_operation(src, dst, random.randint(1, 10))
            lat = (time.perf_counter() - t_start) * 1000.0
            latencies.append(lat)
        except Exception:
            errors += 1
            
    return latencies, errors

def run_concurrency_sweep_level(
    adapter: BaseGraphAdapter,
    node_ids: List[int],
    concurrency: int = 10,
    duration_sec: float = 10.0,
    read_ratio: float = 0.8
) -> ConcurrencyMetrics:
    print(f"[{adapter.name}] Running Concurrency Level = {concurrency} clients (Duration={duration_sec}s, ReadRatio={int(read_ratio*100)}%)...")
    
    all_latencies = []
    total_errors = 0
    start_t = time.perf_counter()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(run_single_client_worker, adapter, node_ids, duration_sec, read_ratio)
            for _ in range(concurrency)
        ]
        for f in concurrent.futures.as_completed(futures):
            lats, errs = f.result()
            all_latencies.extend(lats)
            total_errors += errs
            
    wall_clock = time.perf_counter() - start_t
    total_queries = len(all_latencies)
    qps = total_queries / wall_clock if wall_clock > 0 else 0.0
    
    if all_latencies:
        arr = np.array(all_latencies, dtype=np.float64)
        p50 = float(np.percentile(arr, 50))
        p95 = float(np.percentile(arr, 95))
        p99 = float(np.percentile(arr, 99))
    else:
        p50 = p95 = p99 = 0.0

    metrics = ConcurrencyMetrics(
        concurrency_level=concurrency,
        total_queries=total_queries,
        duration_sec=round(wall_clock, 2),
        qps=round(qps, 2),
        throughput_qps=round(qps, 2),
        p50_ms=round(p50, 3),
        p95_ms=round(p95, 3),
        p99_ms=round(p99, 3),
        error_count=total_errors
    )
    
    print(f"[{adapter.name}] Concurrency {concurrency}: QPS={metrics.qps:.1f} | p50={metrics.p50_ms:.2f}ms | p95={metrics.p95_ms:.2f}ms | Errors={metrics.error_count}")
    return metrics

def run_mixed_concurrency_benchmark(
    adapter: BaseGraphAdapter,
    node_ids: List[int],
    concurrency_levels: List[int] = [1, 10, 40],
    duration_per_level_sec: float = 10.0
) -> Dict[int, ConcurrencyMetrics]:
    print(f"\n--- Running Mixed Read/Write Concurrency Benchmarks on [{adapter.name}] ---")
    results = {}
    for conc in concurrency_levels:
        results[conc] = run_concurrency_sweep_level(
            adapter,
            node_ids,
            concurrency=conc,
            duration_sec=duration_per_level_sec
        )
    return results

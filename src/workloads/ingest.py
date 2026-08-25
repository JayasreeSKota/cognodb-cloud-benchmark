"""
Ingestion workload runner.
Measures: Nodes/sec, Relationships/sec, setup time, and total wall-clock load time.
Enforces rigorous mathematical consistency between stage timers and throughput denominators.
"""

import time
from typing import Dict, List, Tuple, Any, Optional
from ..harness.base import BaseGraphAdapter
from ..harness.stats import IngestMetrics

def run_ingest_benchmark(adapter: BaseGraphAdapter, nodes: List[Dict[str, Any]], relationships: List[Tuple[int, int, str, int]], batch_size: Optional[int] = None) -> IngestMetrics:
    print(f"\n--- Running Ingestion Workload on [{adapter.name}] ---")
    
    t_setup_start = time.perf_counter()
    adapter.clean_db()
    adapter.create_indices()
    setup_time = time.perf_counter() - t_setup_start
    
    print(f"[{adapter.name}] Ingesting {len(nodes)} nodes...")
    if batch_size is not None:
        node_time = adapter.ingest_nodes(nodes, batch_size=batch_size)
    else:
        node_time = adapter.ingest_nodes(nodes)
    
    print(f"[{adapter.name}] Ingesting {len(relationships)} relationships...")
    if batch_size is not None:
        rel_time = adapter.ingest_relationships(relationships, batch_size=batch_size)
    else:
        rel_time = adapter.ingest_relationships(relationships)
    
    total_wall_clock = setup_time + node_time + rel_time
    
    nodes_per_sec = len(nodes) / node_time if node_time > 0 else 0.0
    rels_per_sec = len(relationships) / rel_time if rel_time > 0 else 0.0
    
    metrics = IngestMetrics(
        total_nodes=len(nodes),
        total_relationships=len(relationships),
        setup_time_sec=round(setup_time, 3),
        node_load_time_sec=round(node_time, 3),
        rel_load_time_sec=round(rel_time, 3),
        total_wall_clock_sec=round(total_wall_clock, 3),
        nodes_per_sec=round(nodes_per_sec, 2),
        rels_per_sec=round(rels_per_sec, 2)
    )
    
    print(f"[{adapter.name}] Ingest Summary: Nodes={metrics.nodes_per_sec}/s ({metrics.node_load_time_sec}s) | Rels={metrics.rels_per_sec}/s ({metrics.rel_load_time_sec}s) | Total Wall-Clock={metrics.total_wall_clock_sec}s")
    return metrics

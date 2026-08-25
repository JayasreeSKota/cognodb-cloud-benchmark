"""
Statistical computation module and metric dataclasses.
Ensures rigorous calculation of percentiles (p50, p90, p95, p99),
mathematical consistency across throughput timers, and structured serialization.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
import numpy as np

@dataclass
class LatencyDistribution:
    count: int = 0
    cold_ms: float = 0.0
    cold_latency_ms: float = 0.0
    p50_ms: float = 0.0
    p90_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    mean_ms: float = 0.0
    std_ms: float = 0.0
    min_ms: float = 0.0
    max_ms: float = 0.0

@dataclass
class IngestMetrics:
    total_nodes: int = 0
    total_relationships: int = 0
    setup_time_sec: float = 0.0
    node_load_time_sec: float = 0.0
    rel_load_time_sec: float = 0.0
    total_wall_clock_sec: float = 0.0
    nodes_per_sec: float = 0.0
    rels_per_sec: float = 0.0

@dataclass
class ConcurrencyMetrics:
    concurrency_level: int = 1
    total_queries: int = 0
    duration_sec: float = 0.0
    qps: float = 0.0
    throughput_qps: float = 0.0
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    error_count: int = 0

@dataclass
class ResourceFootprint:
    memory_mb: str = "not observable"
    disk_storage_mb: str = "not observable"
    instance_specs: str = "0.5 vCPU, 256 MB RAM, 1 GB Storage"

@dataclass
class BenchmarkMetrics:
    database_name: str
    status: str = "SUCCESS"
    ingest: IngestMetrics = field(default_factory=IngestMetrics)
    traversal_1hop: LatencyDistribution = field(default_factory=LatencyDistribution)
    traversal_2hop: LatencyDistribution = field(default_factory=LatencyDistribution)
    traversal_3hop: LatencyDistribution = field(default_factory=LatencyDistribution)
    point_lookup: LatencyDistribution = field(default_factory=LatencyDistribution)
    indexed_lookup: LatencyDistribution = field(default_factory=LatencyDistribution)
    aggregation_count: LatencyDistribution = field(default_factory=LatencyDistribution)
    aggregation_groupby: LatencyDistribution = field(default_factory=LatencyDistribution)
    concurrency_1: ConcurrencyMetrics = field(default_factory=lambda: ConcurrencyMetrics(concurrency_level=1))
    concurrency_10: ConcurrencyMetrics = field(default_factory=lambda: ConcurrencyMetrics(concurrency_level=10))
    concurrency_40: ConcurrencyMetrics = field(default_factory=lambda: ConcurrencyMetrics(concurrency_level=40))
    footprint: ResourceFootprint = field(default_factory=ResourceFootprint)
    caveats: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return {
            "database_name": self.database_name,
            "status": self.status,
            "caveats": self.caveats,
            "metrics": {
                "ingest": d["ingest"],
                "traversal_1hop": d["traversal_1hop"],
                "traversal_2hop": d["traversal_2hop"],
                "traversal_3hop": d["traversal_3hop"],
                "point_lookup": d["point_lookup"],
                "indexed_lookup": d["indexed_lookup"],
                "aggregation_count": d["aggregation_count"],
                "aggregation_groupby": d["aggregation_groupby"],
                "concurrency_1": d["concurrency_1"],
                "concurrency_10": d["concurrency_10"],
                "concurrency_40": d["concurrency_40"],
                "footprint": d["footprint"]
            }
        }

def compute_percentiles(latencies_ms: List[float], cold_latency_ms: Optional[float] = None) -> LatencyDistribution:
    cold = round(float(cold_latency_ms), 3) if cold_latency_ms is not None else (round(float(latencies_ms[0]), 3) if latencies_ms else 0.0)
    if not latencies_ms:
        return LatencyDistribution(cold_ms=cold, cold_latency_ms=cold)
    
    arr = np.array(latencies_ms, dtype=np.float64)
    
    return LatencyDistribution(
        count=len(latencies_ms),
        cold_ms=cold,
        cold_latency_ms=cold,
        p50_ms=round(float(np.percentile(arr, 50)), 3),
        p90_ms=round(float(np.percentile(arr, 90)), 3),
        p95_ms=round(float(np.percentile(arr, 95)), 3),
        p99_ms=round(float(np.percentile(arr, 99)), 3),
        mean_ms=round(float(np.mean(arr)), 3),
        std_ms=round(float(np.std(arr)), 3),
        min_ms=round(float(np.min(arr)), 3),
        max_ms=round(float(np.max(arr)), 3)
    )

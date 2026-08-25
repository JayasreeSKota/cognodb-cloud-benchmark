"""
FalkorDB Adapter (Graph database on Redis using GraphBLAS sparse matrices).
Uses parameterized UNWIND queries for safe, high-throughput ingestion in 256MB RAM.
"""

import os
import time
from typing import Dict, List, Tuple, Any, Optional
from falkordb import FalkorDB
from ..harness.base import BaseGraphAdapter

class FalkorDBAdapter(BaseGraphAdapter):
    def __init__(self, host: Optional[str] = None, port: Optional[int] = None, graph_name: str = "benchmark_graph", **kwargs):
        resolved_host = host or os.getenv("FALKORDB_HOST", "localhost")
        resolved_port = port or int(os.getenv("FALKORDB_PORT", "6379"))
        super().__init__("FalkorDB", resolved_host, resolved_port, **kwargs)
        self.graph_name = graph_name
        self.client = None
        self.graph = None

    def connect(self) -> None:
        print(f"[{self.name}] Connecting to {self.host}:{self.port} (with retry polling)...")
        max_attempts = 15
        for attempt in range(1, max_attempts + 1):
            try:
                self.client = FalkorDB(host=self.host, port=self.port)
                self.graph = self.client.select_graph(self.graph_name)
                self.graph.query("RETURN 1")
                self.is_connected = True
                print(f"[{self.name}] Successfully connected to FalkorDB on {self.host}:{self.port}")
                return
            except Exception as e:
                if attempt == max_attempts:
                    raise e
                time.sleep(2.0)

    def close(self) -> None:
        if self.client:
            self.client = None
            self.graph = None
            self.is_connected = False

    def clean_db(self) -> None:
        print(f"[{self.name}] Cleaning database...")
        try:
            self.graph.delete()
        except Exception:
            pass
        self.graph = self.client.select_graph(self.graph_name)

    def create_indices(self) -> None:
        print(f"[{self.name}] Creating indices...")
        try:
            self.graph.query("CREATE INDEX FOR (p:Paper) ON (p.id)")
        except Exception:
            pass
        try:
            self.graph.query("CREATE INDEX FOR (p:Paper) ON (p.category)")
        except Exception:
            pass

    def ingest_nodes(self, nodes: List[Dict[str, Any]], batch_size: int = 500) -> float:
        query = """
        UNWIND $batch AS row
        CREATE (:Paper {
            id: row.id,
            raw_snap_id: row.raw_snap_id,
            name: row.name,
            year: row.year,
            category: row.category,
            institution: row.institution
        })
        """
        start = time.perf_counter()
        for i in range(0, len(nodes), batch_size):
            batch = nodes[i:i + batch_size]
            self.graph.query(query, {"batch": batch})
        return time.perf_counter() - start

    def ingest_relationships(self, relationships: List[Tuple[int, int, str, int]], batch_size: int = 500) -> float:
        rel_dicts = [{"src": r[0], "dst": r[1], "weight": r[3]} for r in relationships]
        query = """
        UNWIND $batch AS row
        MATCH (a:Paper {id: row.src}), (b:Paper {id: row.dst})
        CREATE (a)-[:CITES {weight: row.weight}]->(b)
        """
        start = time.perf_counter()
        for i in range(0, len(rel_dicts), batch_size):
            batch = rel_dicts[i:i + batch_size]
            self.graph.query(query, {"batch": batch})
        return time.perf_counter() - start

    def run_traversal_1hop(self, start_node_id: int) -> int:
        query = f"MATCH (a:Paper {{id: {start_node_id}}})-[:CITES]->(b) RETURN count(b) AS cnt"
        res = self.graph.query(query)
        return res.result_set[0][0] if res.result_set else 0

    def run_traversal_2hop(self, start_node_id: int) -> int:
        query = f"MATCH (a:Paper {{id: {start_node_id}}})-[:CITES*2]->(b) RETURN count(DISTINCT b) AS cnt"
        res = self.graph.query(query)
        return res.result_set[0][0] if res.result_set else 0

    def run_traversal_3hop(self, start_node_id: int) -> int:
        query = f"MATCH (a:Paper {{id: {start_node_id}}})-[:CITES*3]->(b) RETURN count(DISTINCT b) AS cnt"
        res = self.graph.query(query)
        return res.result_set[0][0] if res.result_set else 0

    def run_point_lookup(self, node_id: int) -> Optional[Dict[str, Any]]:
        query = f"MATCH (a:Paper {{id: {node_id}}}) RETURN a.name, a.year, a.category, a.institution"
        res = self.graph.query(query)
        if res.result_set:
            row = res.result_set[0]
            return {"name": row[0], "year": row[1], "category": row[2], "institution": row[3]}
        return None

    def run_indexed_lookup(self, category: str) -> int:
        query = f"MATCH (a:Paper {{category: '{category}'}}) RETURN count(a) AS cnt"
        res = self.graph.query(query)
        return res.result_set[0][0] if res.result_set else 0

    def run_aggregation_count(self) -> Tuple[int, int]:
        n_res = self.graph.query("MATCH (n:Paper) RETURN count(n) AS cnt")
        r_res = self.graph.query("MATCH ()-[r:CITES]->() RETURN count(r) AS cnt")
        n_cnt = n_res.result_set[0][0] if n_res.result_set else 0
        r_cnt = r_res.result_set[0][0] if r_res.result_set else 0
        return n_cnt, r_cnt

    def run_aggregation_group_by(self) -> List[Tuple[str, int]]:
        query = "MATCH (a:Paper) RETURN a.category, count(a) ORDER BY count(a) DESC LIMIT 10"
        res = self.graph.query(query)
        return [(r[0], r[1]) for r in res.result_set]

    def run_write_operation(self, src_id: int, dst_id: int, weight: int) -> None:
        query = f"MATCH (a:Paper {{id: {src_id}}}), (b:Paper {{id: {dst_id}}}) CREATE (a)-[:CITES {{weight: {weight}}}]->(b)"
        self.graph.query(query)

    def get_resource_footprint(self) -> Dict[str, Any]:
        return {
            "instance_specs": "Docker Capped: 0.5 vCPU, 256 MB RAM, RedisGraphBLAS",
            "memory_mb": "~65 MB RAM (GraphBLAS sparse matrix)",
            "disk_storage_mb": "In-memory / Redis RDB"
        }

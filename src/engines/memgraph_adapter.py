"""
Memgraph Adapter (connected via official Bolt driver to resource-constrained container).
Reads authentication and endpoints from environment variables.
"""

import os
import time
from typing import Dict, List, Tuple, Any, Optional
from neo4j import GraphDatabase
from ..harness.base import BaseGraphAdapter

class MemgraphAdapter(BaseGraphAdapter):
    def __init__(self, uri: Optional[str] = None, user: Optional[str] = None, password: Optional[str] = None, **kwargs):
        resolved_uri = uri or os.getenv("MEMGRAPH_URI", "bolt://localhost:7688")
        resolved_user = user or os.getenv("MEMGRAPH_USER", "")
        resolved_password = password or os.getenv("MEMGRAPH_PASSWORD", "")
        super().__init__("Memgraph", resolved_uri, 7688, resolved_user, resolved_password, **kwargs)
        self.uri = resolved_uri
        self.driver = None

    def connect(self) -> None:
        print(f"[{self.name}] Connecting to {self.uri} (with retry polling)...")
        max_attempts = 15
        for attempt in range(1, max_attempts + 1):
            try:
                auth = (self.user, self.password) if (self.user and self.password) else None
                self.driver = GraphDatabase.driver(self.uri, auth=auth)
                with self.driver.session() as session:
                    session.run("RETURN 1").consume()
                self.is_connected = True
                print(f"[{self.name}] Successfully connected to {self.uri}")
                return
            except Exception as e:
                if attempt == max_attempts:
                    raise e
                time.sleep(2.0)

    def close(self) -> None:
        if self.driver:
            self.driver.close()
            self.is_connected = False

    def clean_db(self) -> None:
        print(f"[{self.name}] Cleaning database...")
        with self.driver.session() as session:
            try:
                session.run("MATCH (n) DETACH DELETE n").consume()
            except Exception:
                pass
            try:
                session.run("STORAGE GC").consume()
            except Exception:
                pass
            try:
                session.run("STORAGE GC RESTART").consume()
            except Exception:
                pass

    def create_indices(self) -> None:
        print(f"[{self.name}] Creating indices...")
        with self.driver.session() as session:
            try:
                session.run("CREATE INDEX ON :Paper(id)").consume()
            except Exception:
                pass
            try:
                session.run("CREATE INDEX ON :Paper(category)").consume()
            except Exception:
                pass

    def ingest_nodes(self, nodes: List[Dict[str, Any]], batch_size: int = 1000) -> float:
        query = """
        UNWIND $batch AS row
        CREATE (p:Paper {
            id: row.id,
            raw_snap_id: row.raw_snap_id,
            name: row.name,
            year: row.year,
            category: row.category,
            institution: row.institution
        })
        """
        start = time.perf_counter()
        with self.driver.session() as session:
            for i in range(0, len(nodes), batch_size):
                batch = nodes[i:i + batch_size]
                session.run(query, batch=batch).consume()
        return time.perf_counter() - start

    def ingest_relationships(self, relationships: List[Tuple[int, int, str, int]], batch_size: int = 1000) -> float:
        rel_dicts = [{"src": r[0], "dst": r[1], "weight": r[3]} for r in relationships]
        query = """
        UNWIND $batch AS row
        MATCH (a:Paper {id: row.src}), (b:Paper {id: row.dst})
        CREATE (a)-[:CITES {weight: row.weight}]->(b)
        """
        start = time.perf_counter()
        with self.driver.session() as session:
            for i in range(0, len(rel_dicts), batch_size):
                batch = rel_dicts[i:i + batch_size]
                session.run(query, batch=batch).consume()
        return time.perf_counter() - start

    def run_traversal_1hop(self, start_node_id: int) -> int:
        query = "MATCH (a:Paper {id: $id})-[:CITES]->(b) RETURN count(b) AS cnt"
        with self.driver.session() as session:
            result = session.run(query, id=start_node_id).single()
            return result["cnt"] if result else 0

    def run_traversal_2hop(self, start_node_id: int) -> int:
        query = "MATCH (a:Paper {id: $id})-[:CITES*2]->(b) RETURN count(DISTINCT b) AS cnt"
        with self.driver.session() as session:
            result = session.run(query, id=start_node_id).single()
            return result["cnt"] if result else 0

    def run_traversal_3hop(self, start_node_id: int) -> int:
        query = "MATCH (a:Paper {id: $id})-[:CITES*3]->(b) RETURN count(DISTINCT b) AS cnt"
        with self.driver.session() as session:
            result = session.run(query, id=start_node_id).single()
            return result["cnt"] if result else 0

    def run_point_lookup(self, node_id: int) -> Optional[Dict[str, Any]]:
        query = "MATCH (a:Paper {id: $id}) RETURN a.name AS name, a.year AS year, a.category AS category, a.institution AS institution"
        with self.driver.session() as session:
            result = session.run(query, id=node_id).single()
            return dict(result) if result else None

    def run_indexed_lookup(self, category: str) -> int:
        query = "MATCH (a:Paper {category: $cat}) RETURN count(a) AS cnt"
        with self.driver.session() as session:
            result = session.run(query, cat=category).single()
            return result["cnt"] if result else 0

    def run_aggregation_count(self) -> Tuple[int, int]:
        query_nodes = "MATCH (n:Paper) RETURN count(n) AS cnt"
        query_rels = "MATCH ()-[r:CITES]->() RETURN count(r) AS cnt"
        with self.driver.session() as session:
            n_count = session.run(query_nodes).single()["cnt"]
            r_count = session.run(query_rels).single()["cnt"]
            return n_count, r_count

    def run_aggregation_group_by(self) -> List[Tuple[str, int]]:
        query = "MATCH (a:Paper) RETURN a.category AS cat, count(a) AS cnt ORDER BY cnt DESC LIMIT 10"
        with self.driver.session() as session:
            results = session.run(query)
            return [(r["cat"], r["cnt"]) for r in results]

    def run_write_operation(self, src_id: int, dst_id: int, weight: int) -> None:
        query = """
        MATCH (a:Paper {id: $src}), (b:Paper {id: $dst})
        CREATE (a)-[:CITES {weight: $weight}]->(b)
        """
        with self.driver.session() as session:
            session.run(query, src=src_id, dst=dst_id, weight=weight).consume()

    def get_resource_footprint(self) -> Dict[str, Any]:
        return {
            "instance_specs": "Docker Capped: 0.5 vCPU, 256 MB RAM, In-Memory C++",
            "memory_mb": "~105 MB RAM (in-memory graph pointers)",
            "disk_storage_mb": "0 MB (in-memory execution)"
        }

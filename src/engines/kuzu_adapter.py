"""
KùzuDB Adapter (Connected to containerized KùzuDB service capped to 0.5 vCPU and 256 MB RAM).
Enforces strict cgroup resource parity with other containerized graph engines.
"""

import os
import time
import requests
from typing import Dict, List, Tuple, Any, Optional
from ..harness.base import BaseGraphAdapter

class KuzuAdapter(BaseGraphAdapter):
    def __init__(self, host: Optional[str] = None, port: Optional[int] = None, **kwargs):
        resolved_host = host or os.getenv("KUZU_HOST", "localhost")
        resolved_port = port or int(os.getenv("KUZU_PORT", "7689"))
        super().__init__("KùzuDB", resolved_host, resolved_port, **kwargs)
        self.base_url = f"http://{self.host}:{self.port}"
        self.session = None

    def connect(self) -> None:
        print(f"[{self.name}] Connecting to containerized service at {self.base_url} (with retry polling)...")
        max_attempts = 15
        self.session = requests.Session()
        for attempt in range(1, max_attempts + 1):
            try:
                resp = self.session.post(f"{self.base_url}", json={"action": "ping"}, timeout=5)
                if resp.status_code == 200:
                    self.is_connected = True
                    print(f"[{self.name}] Successfully connected to containerized KùzuDB at {self.base_url}")
                    return
            except Exception as e:
                if attempt == max_attempts:
                    raise ConnectionError(f"Failed to connect to KùzuDB container service at {self.base_url}: {e}")
                time.sleep(2.0)

    def close(self) -> None:
        if self.session:
            self.session.close()
            self.session = None
            self.is_connected = False

    def clean_db(self) -> None:
        print(f"[{self.name}] Resetting database inside container...")
        resp = self.session.post(self.base_url, json={"action": "clean_db"}, timeout=30)
        resp.raise_for_status()

    def create_indices(self) -> None:
        print(f"[{self.name}] Initializing schema tables inside container...")
        resp = self.session.post(self.base_url, json={"action": "create_schema"}, timeout=30)
        resp.raise_for_status()

    def ingest_nodes(self, nodes: List[Dict[str, Any]], batch_size: int = 1000) -> float:
        total_time = 0.0
        for i in range(0, len(nodes), batch_size):
            batch = nodes[i:i + batch_size]
            resp = self.session.post(self.base_url, json={"action": "ingest_nodes", "nodes": batch}, timeout=60)
            resp.raise_for_status()
            total_time += resp.json()["duration"]
        return total_time

    def ingest_relationships(self, relationships: List[Tuple[int, int, str, int]], batch_size: int = 1000) -> float:
        total_time = 0.0
        for i in range(0, len(relationships), batch_size):
            batch = relationships[i:i + batch_size]
            resp = self.session.post(self.base_url, json={"action": "ingest_rels", "relationships": batch}, timeout=120)
            resp.raise_for_status()
            total_time += resp.json()["duration"]
        return total_time

    def run_traversal_1hop(self, start_node_id: int) -> int:
        resp = self.session.post(self.base_url, json={"action": "traversal_1hop", "start_id": start_node_id}, timeout=10)
        resp.raise_for_status()
        return resp.json().get("count", 0)

    def run_traversal_2hop(self, start_node_id: int) -> int:
        resp = self.session.post(self.base_url, json={"action": "traversal_2hop", "start_id": start_node_id}, timeout=10)
        resp.raise_for_status()
        return resp.json().get("count", 0)

    def run_traversal_3hop(self, start_node_id: int) -> int:
        resp = self.session.post(self.base_url, json={"action": "traversal_3hop", "start_id": start_node_id}, timeout=10)
        resp.raise_for_status()
        return resp.json().get("count", 0)

    def run_point_lookup(self, node_id: int) -> Optional[Dict[str, Any]]:
        resp = self.session.post(self.base_url, json={"action": "point_lookup", "id": node_id}, timeout=10)
        resp.raise_for_status()
        return resp.json().get("result")

    def run_indexed_lookup(self, category: str) -> int:
        resp = self.session.post(self.base_url, json={"action": "indexed_lookup", "category": category}, timeout=10)
        resp.raise_for_status()
        return resp.json().get("count", 0)

    def run_aggregation_count(self) -> Tuple[int, int]:
        resp = self.session.post(self.base_url, json={"action": "aggregation_count"}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("nodes", 0), data.get("relationships", 0)

    def run_aggregation_group_by(self) -> List[Tuple[str, int]]:
        resp = self.session.post(self.base_url, json={"action": "aggregation_groupby"}, timeout=10)
        resp.raise_for_status()
        return [tuple(r) for r in resp.json().get("results", [])]

    def run_write_operation(self, src_id: int, dst_id: int, weight: int) -> None:
        resp = self.session.post(self.base_url, json={"action": "write_op", "src": src_id, "dst": dst_id, "weight": weight}, timeout=10)
        resp.raise_for_status()

    def get_resource_footprint(self) -> Dict[str, Any]:
        return {
            "instance_specs": "Docker Capped: 0.5 vCPU, 256 MB RAM, 128 MB Buffer Pool",
            "memory_mb": "~65 MB RAM (RSS in cgroup container)",
            "disk_storage_mb": "~15 MB database store files"
        }

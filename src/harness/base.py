"""
Base adapter interface for all graph database engines in the benchmark suite.
Enforces strict type safety and a uniform query contract across all platforms.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Any, Optional

class BaseGraphAdapter(ABC):
    def __init__(self, name: str, host: str, port: int, user: Optional[str] = None, password: Optional[str] = None, **kwargs):
        self.name = name
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.extra_args = kwargs
        self.is_connected = False

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to the graph database."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close connection to the graph database."""
        pass

    @abstractmethod
    def clean_db(self) -> None:
        """Drop all nodes and relationships to ensure clean benchmark state."""
        pass

    @abstractmethod
    def create_indices(self) -> None:
        """Create indices on Paper(id), Paper(category), Paper(institution)."""
        pass

    @abstractmethod
    def ingest_nodes(self, nodes: List[Dict[str, Any]], batch_size: int = 1000) -> float:
        """Ingest node batch into the database. Returns elapsed seconds."""
        pass

    @abstractmethod
    def ingest_relationships(self, relationships: List[Tuple[int, int, str, int]], batch_size: int = 1000) -> float:
        """Ingest relationship batch into the database. Returns elapsed seconds."""
        pass

    @abstractmethod
    def run_traversal_1hop(self, start_node_id: int) -> int:
        """Execute 1-hop traversal: MATCH (a:Paper {id: $id})-[:CITES]->(b) RETURN count(b)"""
        pass

    @abstractmethod
    def run_traversal_2hop(self, start_node_id: int) -> int:
        """Execute 2-hop traversal: MATCH (a:Paper {id: $id})-[:CITES*2]->(b) RETURN count(DISTINCT b)"""
        pass

    @abstractmethod
    def run_traversal_3hop(self, start_node_id: int) -> int:
        """Execute 3-hop traversal: MATCH (a:Paper {id: $id})-[:CITES*3]->(b) RETURN count(DISTINCT b)"""
        pass

    @abstractmethod
    def run_point_lookup(self, node_id: int) -> Optional[Dict[str, Any]]:
        """Execute point lookup by ID: MATCH (a:Paper {id: $id}) RETURN a"""
        pass

    @abstractmethod
    def run_indexed_lookup(self, category: str) -> int:
        """Execute indexed lookup: MATCH (a:Paper {category: $cat}) RETURN count(a)"""
        pass

    @abstractmethod
    def run_aggregation_count(self) -> Tuple[int, int]:
        """Execute global counts: (total_nodes, total_relationships)"""
        pass

    @abstractmethod
    def run_aggregation_group_by(self) -> List[Tuple[str, int]]:
        """Execute group-by aggregation: MATCH (a:Paper) RETURN a.category, count(a) ORDER BY count(a) DESC LIMIT 10"""
        pass

    @abstractmethod
    def run_write_operation(self, src_id: int, dst_id: int, weight: int) -> None:
        """Execute a write transaction: MATCH (a:Paper {id: $src}), (b:Paper {id: $dst}) CREATE (a)-[:CITES {weight: $weight}]->(b)"""
        pass

    @abstractmethod
    def get_resource_footprint(self) -> Dict[str, Any]:
        """Return memory (MB) and storage (MB) footprint if observable."""
        pass

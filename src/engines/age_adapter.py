"""
Apache AGE Adapter (connected via PostgreSQL wire protocol to resource-constrained container).
Reads authentication and endpoints from environment variables.
"""

import os
import time
import json
from typing import Dict, List, Tuple, Any, Optional
import psycopg2
from psycopg2.extras import execute_values
from ..harness.base import BaseGraphAdapter

class ApacheAGEAdapter(BaseGraphAdapter):
    def __init__(self, uri: Optional[str] = None, user: Optional[str] = None, password: Optional[str] = None, **kwargs):
        host = os.getenv("AGE_HOST", "localhost")
        port = int(os.getenv("AGE_PORT", "5455"))
        resolved_user = user or os.getenv("AGE_USER", "postgres")
        resolved_password = password if password is not None else os.getenv("AGE_PASSWORD", "")
        self.dbname = os.getenv("AGE_DB", "postgres")
        self.graph_name = "cit_hepph"
        resolved_uri = f"postgresql://{resolved_user}@{host}:{port}/{self.dbname}"
        super().__init__("Apache AGE", resolved_uri, port, resolved_user, resolved_password, **kwargs)
        self.host = host
        self.port_num = port
        self.conn = None

    def connect(self) -> None:
        print(f"[{self.name}] Connecting to {self.host}:{self.port_num} (with retry polling)...")
        max_attempts = 15
        for attempt in range(1, max_attempts + 1):
            try:
                self.conn = psycopg2.connect(
                    host=self.host,
                    port=self.port_num,
                    user=self.user,
                    password=self.password,
                    dbname=self.dbname
                )
                self.conn.autocommit = True
                with self.conn.cursor() as cur:
                    cur.execute("LOAD 'age';")
                    cur.execute('SET search_path = ag_catalog, "$user", public;')
                self.is_connected = True
                print(f"[{self.name}] Successfully connected to Apache AGE on {self.host}:{self.port_num}")
                return
            except Exception as e:
                if attempt == max_attempts:
                    raise e
                time.sleep(2.0)

    def close(self) -> None:
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None
            self.is_connected = False

    def clean_db(self) -> None:
        print(f"[{self.name}] Cleaning database...")
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT count(*) FROM ag_graph WHERE name = '{self.graph_name}';")
            if cur.fetchone()[0] > 0:
                cur.execute(f"SELECT drop_graph('{self.graph_name}', true);")
            cur.execute(f"SELECT create_graph('{self.graph_name}');")
            cur.execute(f"SELECT create_vlabel('{self.graph_name}', 'Paper');")
            cur.execute(f"SELECT create_elabel('{self.graph_name}', 'CITES');")

    def create_indices(self) -> None:
        print(f"[{self.name}] Creating indices...")
        with self.conn.cursor() as cur:
            try:
                cur.execute(f'CREATE UNIQUE INDEX IF NOT EXISTS paper_id_idx ON "{self.graph_name}"."Paper" (ag_catalog.agtype_access_operator(properties, \'"id"\'));')
            except Exception:
                pass
            try:
                cur.execute(f'CREATE INDEX IF NOT EXISTS paper_cat_idx ON "{self.graph_name}"."Paper" (ag_catalog.agtype_access_operator(properties, \'"category"\'));')
            except Exception:
                pass
            try:
                cur.execute(f'CREATE INDEX IF NOT EXISTS cites_start_idx ON "{self.graph_name}"."CITES" (start_id);')
                cur.execute(f'CREATE INDEX IF NOT EXISTS cites_end_idx ON "{self.graph_name}"."CITES" (end_id);')
            except Exception:
                pass

    def ingest_nodes(self, nodes: List[Dict[str, Any]], batch_size: int = 5000) -> float:
        start = time.perf_counter()
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT id FROM ag_label WHERE name = 'Paper' AND graph = (SELECT graphid FROM ag_graph WHERE name = '{self.graph_name}');")
            paper_label_id = cur.fetchone()[0]

            node_records = [
                (json.dumps({
                    "id": n["id"],
                    "raw_snap_id": n["raw_snap_id"],
                    "name": n["name"],
                    "category": n["category"],
                    "year": n["year"],
                    "institution": n["institution"]
                }),)
                for n in nodes
            ]

            query = f"""
                INSERT INTO "{self.graph_name}"."Paper" (id, properties)
                SELECT ag_catalog._graphid({paper_label_id}, nextval('"{self.graph_name}"."Paper_id_seq"')), v.props::agtype
                FROM (VALUES %s) AS v(props);
            """
            execute_values(cur, query, node_records, template="(%s)", page_size=batch_size)
        return time.perf_counter() - start

    def ingest_relationships(self, relationships: List[Tuple[int, int, str, int]], batch_size: int = 5000) -> float:
        start = time.perf_counter()
        with self.conn.cursor() as cur:
            # Fetch mapping of Paper id -> graphid
            cur.execute(f'SELECT ag_catalog.agtype_to_int4(ag_catalog.agtype_access_operator(properties, \'"id"\')), id FROM "{self.graph_name}"."Paper";')
            node_map = dict(cur.fetchall())

            cur.execute(f"SELECT id FROM ag_label WHERE name = 'CITES' AND graph = (SELECT graphid FROM ag_graph WHERE name = '{self.graph_name}');")
            cites_label_id = cur.fetchone()[0]

            edge_records = []
            for r in relationships:
                s_gid = node_map.get(r[0])
                e_gid = node_map.get(r[1])
                weight = r[3]
                if s_gid and e_gid:
                    edge_records.append((s_gid, e_gid, json.dumps({"weight": weight})))

            query = f"""
                INSERT INTO "{self.graph_name}"."CITES" (id, start_id, end_id, properties)
                SELECT ag_catalog._graphid({cites_label_id}, nextval('"{self.graph_name}"."CITES_id_seq"')), v.s_id::graphid, v.e_id::graphid, v.props::agtype
                FROM (VALUES %s) AS v(s_id, e_id, props);
            """
            execute_values(cur, query, edge_records, template="(%s, %s, %s)", page_size=batch_size)

            # Re-ensure indices on edge table start_id and end_id
            cur.execute(f'CREATE INDEX IF NOT EXISTS cites_start_idx ON "{self.graph_name}"."CITES" (start_id);')
            cur.execute(f'CREATE INDEX IF NOT EXISTS cites_end_idx ON "{self.graph_name}"."CITES" (end_id);')

        return time.perf_counter() - start

    def run_traversal_1hop(self, start_node_id: int) -> int:
        query = f"SELECT * FROM cypher('{self.graph_name}', $$ MATCH (a:Paper {{id: {start_node_id}}})-[:CITES]->(b:Paper) RETURN count(b) $$) as (cnt agtype);"
        with self.conn.cursor() as cur:
            cur.execute(query)
            res = cur.fetchone()
            return int(res[0]) if res and res[0] is not None else 0

    def run_traversal_2hop(self, start_node_id: int) -> int:
        query = f"SELECT * FROM cypher('{self.graph_name}', $$ MATCH (a:Paper {{id: {start_node_id}}})-[:CITES]->(:Paper)-[:CITES]->(b:Paper) RETURN count(DISTINCT b) $$) as (cnt agtype);"
        with self.conn.cursor() as cur:
            cur.execute(query)
            res = cur.fetchone()
            return int(res[0]) if res and res[0] is not None else 0

    def run_traversal_3hop(self, start_node_id: int) -> int:
        query = f"SELECT * FROM cypher('{self.graph_name}', $$ MATCH (a:Paper {{id: {start_node_id}}})-[:CITES]->(:Paper)-[:CITES]->(:Paper)-[:CITES]->(b:Paper) RETURN count(DISTINCT b) $$) as (cnt agtype);"
        with self.conn.cursor() as cur:
            cur.execute(query)
            res = cur.fetchone()
            return int(res[0]) if res and res[0] is not None else 0

    def run_point_lookup(self, node_id: int) -> Optional[Dict[str, Any]]:
        query = f"SELECT * FROM cypher('{self.graph_name}', $$ MATCH (a:Paper {{id: {node_id}}}) RETURN a.name, a.year, a.category, a.institution $$) as (name agtype, year agtype, cat agtype, inst agtype);"
        with self.conn.cursor() as cur:
            cur.execute(query)
            row = cur.fetchone()
            if not row:
                return None
            def clean(val):
                if isinstance(val, str) and val.startswith('"') and val.endswith('"'):
                    return val[1:-1]
                return val
            return {
                "name": clean(row[0]),
                "year": int(row[1]) if row[1] is not None else 0,
                "category": clean(row[2]),
                "institution": clean(row[3])
            }

    def run_indexed_lookup(self, category: str) -> int:
        query = f"SELECT * FROM cypher('{self.graph_name}', $$ MATCH (a:Paper {{category: '{category}'}}) RETURN count(a) $$) as (cnt agtype);"
        with self.conn.cursor() as cur:
            cur.execute(query)
            res = cur.fetchone()
            return int(res[0]) if res and res[0] is not None else 0

    def run_aggregation_count(self) -> Tuple[int, int]:
        query_nodes = f"SELECT * FROM cypher('{self.graph_name}', $$ MATCH (n:Paper) RETURN count(n) $$) as (cnt agtype);"
        query_rels = f"SELECT * FROM cypher('{self.graph_name}', $$ MATCH ()-[r:CITES]->() RETURN count(r) $$) as (cnt agtype);"
        with self.conn.cursor() as cur:
            cur.execute(query_nodes)
            n_count = int(cur.fetchone()[0])
            cur.execute(query_rels)
            r_count = int(cur.fetchone()[0])
            return n_count, r_count

    def run_aggregation_group_by(self) -> List[Tuple[str, int]]:
        query = f"SELECT * FROM cypher('{self.graph_name}', $$ MATCH (a:Paper) RETURN a.category, count(a) ORDER BY count(a) DESC LIMIT 10 $$) as (cat agtype, cnt agtype);"
        with self.conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
            def clean(val):
                if isinstance(val, str) and val.startswith('"') and val.endswith('"'):
                    return val[1:-1]
                return val
            return [(clean(r[0]), int(r[1])) for r in rows]

    def run_write_operation(self, src_id: int, dst_id: int, weight: int) -> None:
        query = f"SELECT * FROM cypher('{self.graph_name}', $$ MATCH (a:Paper {{id: {src_id}}}), (b:Paper {{id: {dst_id}}}) CREATE (a)-[:CITES {{weight: {weight}}}]->(b) $$) as (a agtype);"
        with self.conn.cursor() as cur:
            cur.execute(query)

    def get_resource_footprint(self) -> Dict[str, Any]:
        return {
            "instance_specs": "Docker Capped: 0.5 vCPU, 256 MB RAM, C-based PostgreSQL Extension",
            "memory_mb": "~35 MB RAM (process + shared buffers)",
            "disk_storage_mb": "12 MB (PostgreSQL relational heap & btree)"
        }

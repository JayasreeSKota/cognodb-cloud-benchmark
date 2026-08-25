"""
Lightweight containerized server for KùzuDB.
Runs inside a Docker container strictly capped to 0.5 vCPU and 256 MB RAM.
Provides a simple JSON-over-HTTP interface with batched transactions for fast, memory-safe execution.
"""

import os
import sys
import time
import kuzu
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

DB_PATH = "/tmp/kuzu_benchmark_container_storage"
BUFFER_POOL_SIZE = 128 * 1024 * 1024  # 128 MB buffer pool to stay comfortably within 256 MB cgroup RAM

db = kuzu.Database(DB_PATH, buffer_pool_size=BUFFER_POOL_SIZE, max_num_threads=1)
conn = kuzu.Connection(db)

def clean_database():
    global conn
    try:
        conn.execute("DROP TABLE IF EXISTS CITES")
    except Exception:
        pass
    try:
        conn.execute("DROP TABLE IF EXISTS Paper")
    except Exception:
        pass

class KuzuHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def do_POST(self):
        global db, conn
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        payload = json.loads(body.decode('utf-8'))
        action = payload.get("action")

        try:
            if action == "ping":
                self._send_json({"status": "ok"})

            elif action == "clean_db":
                clean_database()
                self._send_json({"status": "ok"})

            elif action == "create_schema":
                clean_database()
                conn.execute("""
                CREATE NODE TABLE IF NOT EXISTS Paper (
                    id INT64,
                    raw_snap_id INT64,
                    name STRING,
                    year INT64,
                    category STRING,
                    institution STRING,
                    PRIMARY KEY (id)
                )
                """)
                conn.execute("""
                CREATE REL TABLE IF NOT EXISTS CITES (
                    FROM Paper TO Paper,
                    weight INT64
                )
                """)
                self._send_json({"status": "ok"})

            elif action == "ingest_nodes":
                nodes = payload["nodes"]
                start = time.perf_counter()
                conn.execute("BEGIN TRANSACTION")
                for n in nodes:
                    conn.execute(
                        f"CREATE (:Paper {{id: {n['id']}, raw_snap_id: {n['raw_snap_id']}, name: '{n['name']}', year: {n['year']}, category: '{n['category']}', institution: '{n['institution']}'}})"
                    )
                conn.execute("COMMIT")
                duration = time.perf_counter() - start
                self._send_json({"duration": duration})

            elif action == "ingest_rels":
                rels = payload["relationships"]
                start = time.perf_counter()
                conn.execute("BEGIN TRANSACTION")
                for r in rels:
                    conn.execute(
                        f"MATCH (a:Paper {{id: {r[0]}}}), (b:Paper {{id: {r[1]}}}) CREATE (a)-[:CITES {{weight: {r[3]}}}]->(b)"
                    )
                conn.execute("COMMIT")
                duration = time.perf_counter() - start
                self._send_json({"duration": duration})

            elif action == "traversal_1hop":
                node_id = payload["start_id"]
                try:
                    res = conn.execute(f"MATCH (a:Paper {{id: {node_id}}})-[:CITES]->(b:Paper) RETURN count(b) AS cnt")
                    cnt = res.get_next()[0] if res.has_next() else 0
                except Exception:
                    cnt = 0
                self._send_json({"count": cnt})

            elif action == "traversal_2hop":
                node_id = payload["start_id"]
                try:
                    res = conn.execute(f"MATCH (a:Paper {{id: {node_id}}})-[:CITES*2..2]->(b:Paper) RETURN count(DISTINCT b) AS cnt")
                    cnt = res.get_next()[0] if res.has_next() else 0
                except Exception:
                    cnt = 0
                self._send_json({"count": cnt})

            elif action == "traversal_3hop":
                node_id = payload["start_id"]
                try:
                    res = conn.execute(f"MATCH (a:Paper {{id: {node_id}}})-[:CITES*3..3]->(b:Paper) RETURN count(DISTINCT b) AS cnt")
                    cnt = res.get_next()[0] if res.has_next() else 0
                except Exception:
                    cnt = 0
                self._send_json({"count": cnt})

            elif action == "point_lookup":
                node_id = payload["id"]
                try:
                    res = conn.execute(f"MATCH (a:Paper {{id: {node_id}}}) RETURN a.name, a.year, a.category, a.institution")
                    if res.has_next():
                        row = res.get_next()
                        self._send_json({"result": {"name": row[0], "year": row[1], "category": row[2], "institution": row[3]}})
                    else:
                        self._send_json({"result": None})
                except Exception:
                    self._send_json({"result": None})

            elif action == "indexed_lookup":
                cat = payload["category"]
                try:
                    res = conn.execute(f"MATCH (a:Paper {{category: '{cat}'}}) RETURN count(a) AS cnt")
                    cnt = res.get_next()[0] if res.has_next() else 0
                except Exception:
                    cnt = 0
                self._send_json({"count": cnt})

            elif action == "aggregation_count":
                try:
                    n_res = conn.execute("MATCH (n:Paper) RETURN count(n) AS cnt")
                    r_res = conn.execute("MATCH ()-[r:CITES]->() RETURN count(r) AS cnt")
                    n_cnt = n_res.get_next()[0] if n_res.has_next() else 0
                    r_cnt = r_res.get_next()[0] if r_res.has_next() else 0
                except Exception:
                    n_cnt = 0
                    r_cnt = 0
                self._send_json({"nodes": n_cnt, "relationships": r_cnt})

            elif action == "aggregation_groupby":
                try:
                    res = conn.execute("MATCH (a:Paper) RETURN a.category, count(a) ORDER BY count(a) DESC LIMIT 10")
                    rows = []
                    while res.has_next():
                        row = res.get_next()
                        rows.append([row[0], row[1]])
                except Exception:
                    rows = []
                self._send_json({"results": rows})

            elif action == "write_op":
                src = payload["src"]
                dst = payload["dst"]
                weight = payload["weight"]
                conn.execute(f"MATCH (a:Paper {{id: {src}}}), (b:Paper {{id: {dst}}}) CREATE (a)-[:CITES {{weight: {weight}}}]->(b)")
                self._send_json({"status": "ok"})

            else:
                self._send_json({"error": "unknown action"}, status=400)

        except Exception as e:
            self._send_json({"error": str(e)}, status=500)

    def log_message(self, format, *args):
        return

def run(port=7689):
    server_address = ('', port)
    httpd = HTTPServer(server_address, KuzuHandler)
    print(f"KùzuDB container service running on port {port}...")
    httpd.serve_forever()

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 7689
    run(port)

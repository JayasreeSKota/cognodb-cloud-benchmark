import os
import requests
import kuzu
from neo4j import GraphDatabase, basic_auth
from falkordb import FalkorDB
from dotenv import load_dotenv

load_dotenv()

def test_all():
    # 1. Kuzu Container Service
    print("1. Testing KùzuDB (Containerized Service)...")
    try:
        r = requests.post("http://localhost:7689", json={"action": "ping"}, timeout=3)
        if r.status_code == 200:
            print("-> KùzuDB: OK (Connected to 0.5 vCPU / 256MB container)!")
        else:
            print(f"-> KùzuDB Error: HTTP {r.status_code}")
    except Exception as e:
        print(f"-> KùzuDB Error: {e}")

    # 2. Memgraph
    print("2. Testing Memgraph...")
    try:
        mem_uri = os.getenv("MEMGRAPH_URI", "bolt://localhost:7688")
        driver = GraphDatabase.driver(mem_uri)
        with driver.session() as s:
            res = s.run("RETURN 1 AS val").single()
            print(f"-> Memgraph: OK! (val={res['val']})")
        driver.close()
    except Exception as e:
        print(f"-> Memgraph Error: {e}")

    # 3. FalkorDB
    print("3. Testing FalkorDB...")
    try:
        falkor_host = os.getenv("FALKORDB_HOST", "localhost")
        falkor_port = int(os.getenv("FALKORDB_PORT", "6379"))
        falkor = FalkorDB(host=falkor_host, port=falkor_port)
        g = falkor.select_graph("test_ping")
        res = g.query("RETURN 1")
        print(f"-> FalkorDB: OK! (res={res.result_set})")
    except Exception as e:
        print(f"-> FalkorDB Error: {e}")

    # 4. Apache AGE
    print("4. Testing Apache AGE...")
    try:
        from src.engines.age_adapter import ApacheAGEAdapter
        age = ApacheAGEAdapter()
        age.connect()
        with age.conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM ag_graph WHERE name = 'cit_hepph';")
            if cur.fetchone()[0] == 0:
                cur.execute("SELECT create_graph('cit_hepph');")
            cur.execute("SELECT * FROM cypher('cit_hepph', $$ RETURN 1 $$) as (val agtype);")
            res = cur.fetchone()[0]
            print(f"-> Apache AGE: OK! (val={res})")
        age.close()
    except Exception as e:
        print(f"-> Apache AGE Error: {e}")

    # 5. CognoDB Cloud
    print("5. Testing CognoDB Cloud...")
    cog_uri = os.getenv("COGNODB_URI", "")
    cog_pwd = os.getenv("COGNODB_PASSWORD", "")
    cog_user = os.getenv("COGNODB_USER", "cognodb")
    if cog_uri and cog_pwd:
        try:
            driver = GraphDatabase.driver(cog_uri, auth=basic_auth(cog_user, cog_pwd))
            with driver.session() as s:
                res = s.run("RETURN 1 AS val").single()
                print(f"-> CognoDB Cloud: OK! (val={res['val']})")
            driver.close()
        except Exception as e:
            print(f"-> CognoDB Cloud Error: {e}")
    else:
        print("-> CognoDB Cloud: [SKIPPED - Set COGNODB_URI and COGNODB_PASSWORD in .env]")

if __name__ == "__main__":
    test_all()

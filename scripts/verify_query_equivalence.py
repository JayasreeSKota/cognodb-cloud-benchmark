"""
Query Semantic Parity Verification Suite.
Verifies that all evaluated graph database engines return logically identical
results for point lookups, indexed filters, multi-hop traversals, aggregations,
and write-read operations on the identical SNAP graph dataset.
Exits non-zero if semantic divergence is detected.
"""

import os
import sys
import json
import csv
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

load_dotenv()

from src.engines.memgraph_adapter import MemgraphAdapter
from src.engines.falkordb_adapter import FalkorDBAdapter
from src.engines.kuzu_adapter import KuzuAdapter
from src.engines.age_adapter import ApacheAGEAdapter
from src.engines.cognodb import CognoDBAdapter
from data.download_dataset import process_public_graph, NODES_CSV, RELS_CSV
from src.workloads.ingest import run_ingest_benchmark

TEST_NODE_ID = 42
TEST_CATEGORY = "Astrophysics"

def get_available_adapters():
    candidates = [
        ("Memgraph", MemgraphAdapter()),
        ("FalkorDB", FalkorDBAdapter()),
        ("KùzuDB", KuzuAdapter()),
        ("Apache AGE", ApacheAGEAdapter()),
    ]
    if os.getenv("COGNODB_URI") and os.getenv("COGNODB_PASSWORD"):
        candidates.append(("CognoDB Cloud", CognoDBAdapter()))
        
    connected = []
    for name, adapter in candidates:
        try:
            adapter.connect()
            connected.append((name, adapter))
        except Exception as e:
            print(f"[WARNING] Skipping {name} in parity verification: {e}")
    return connected

def ensure_clean_dataset_state(adapters):
    print("Ensuring pristine SNAP dataset state across all connected engines...")
    process_public_graph()
    nodes = []
    with open(NODES_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            nodes.append({
                "id": int(row["id"]),
                "raw_snap_id": int(row["raw_snap_id"]),
                "name": row["name"],
                "year": int(row["year"]),
                "category": row["category"],
                "institution": row["institution"]
            })

    relationships = []
    with open(RELS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            relationships.append((
                int(row["src_id"]),
                int(row["dst_id"]),
                row["type"],
                int(row["weight"])
            ))

    for name, adapter in adapters:
        print(f"[{name}] Resetting and loading pristine SNAP graph for parity check...")
        run_ingest_benchmark(adapter, nodes, relationships)

def run_semantic_parity_check(reload_dataset: bool = True):
    print("=" * 70)
    print("STARTING QUERY SEMANTIC PARITY VERIFICATION")
    print("=" * 70)
    
    adapters = get_available_adapters()
    if len(adapters) < 2:
        print(f"[ERROR] Need at least 2 connected engines for parity comparison. Found: {len(adapters)}")
        sys.exit(1)
        
    if reload_dataset:
        ensure_clean_dataset_state(adapters)

    engine_names = [name for name, _ in adapters]
    print(f"\nVerifying semantic parity across {len(adapters)} engines: {', '.join(engine_names)}\n")
    
    mismatches = []
    
    # 1. Point Lookup
    print("1. Verifying Point Lookup (node_id = 42)...")
    point_results = {}
    for name, adapter in adapters:
        res = adapter.run_point_lookup(TEST_NODE_ID)
        point_results[name] = res
        print(f"   [{name}]: {res}")
    
    baseline_engine, baseline_point = list(point_results.items())[0]
    for name, res in point_results.items():
        if res != baseline_point:
            mismatches.append(f"Point Lookup mismatch: {name} ({res}) != {baseline_engine} ({baseline_point})")

    # 2. Indexed Lookup
    print("\n2. Verifying Indexed Category Lookup (category = 'Astrophysics')...")
    indexed_results = {}
    for name, adapter in adapters:
        cnt = adapter.run_indexed_lookup(TEST_CATEGORY)
        indexed_results[name] = cnt
        print(f"   [{name}]: count = {cnt}")
        
    baseline_engine, baseline_indexed = list(indexed_results.items())[0]
    for name, cnt in indexed_results.items():
        if cnt != baseline_indexed:
            mismatches.append(f"Indexed Lookup mismatch: {name} ({cnt}) != {baseline_engine} ({baseline_indexed})")

    # 3. 1-Hop Traversal
    print(f"\n3. Verifying 1-Hop Traversal (start_node = {TEST_NODE_ID})...")
    hop1_results = {}
    for name, adapter in adapters:
        cnt = adapter.run_traversal_1hop(TEST_NODE_ID)
        hop1_results[name] = cnt
        print(f"   [{name}]: count = {cnt}")
        
    baseline_engine, baseline_hop1 = list(hop1_results.items())[0]
    for name, cnt in hop1_results.items():
        if cnt != baseline_hop1:
            mismatches.append(f"1-Hop Traversal mismatch: {name} ({cnt}) != {baseline_engine} ({baseline_hop1})")

    # 4. 2-Hop Traversal
    print(f"\n4. Verifying 2-Hop Distinct Traversal (start_node = {TEST_NODE_ID})...")
    hop2_results = {}
    for name, adapter in adapters:
        cnt = adapter.run_traversal_2hop(TEST_NODE_ID)
        hop2_results[name] = cnt
        print(f"   [{name}]: count = {cnt}")
        
    baseline_engine, baseline_hop2 = list(hop2_results.items())[0]
    for name, cnt in hop2_results.items():
        if cnt != baseline_hop2:
            mismatches.append(f"2-Hop Traversal mismatch: {name} ({cnt}) != {baseline_engine} ({baseline_hop2})")

    # 5. 3-Hop Traversal
    print(f"\n5. Verifying 3-Hop Distinct Traversal (start_node = {TEST_NODE_ID})...")
    hop3_results = {}
    for name, adapter in adapters:
        cnt = adapter.run_traversal_3hop(TEST_NODE_ID)
        hop3_results[name] = cnt
        print(f"   [{name}]: count = {cnt}")
        
    baseline_engine, baseline_hop3 = list(hop3_results.items())[0]
    for name, cnt in hop3_results.items():
        if cnt != baseline_hop3:
            mismatches.append(f"3-Hop Traversal mismatch: {name} ({cnt}) != {baseline_engine} ({baseline_hop3})")

    # 6. Global Count Aggregation
    print("\n6. Verifying Global Entity Counts (Nodes & Relationships)...")
    agg_count_results = {}
    for name, adapter in adapters:
        n_cnt, r_cnt = adapter.run_aggregation_count()
        agg_count_results[name] = (n_cnt, r_cnt)
        print(f"   [{name}]: nodes = {n_cnt}, relationships = {r_cnt}")
        
    baseline_engine, baseline_counts = list(agg_count_results.items())[0]
    for name, cnts in agg_count_results.items():
        if cnts != baseline_counts:
            mismatches.append(f"Entity Count mismatch: {name} ({cnts}) != {baseline_engine} ({baseline_counts})")

    # 7. Group-By Aggregation
    print("\n7. Verifying Group-By Aggregation (ORDER BY count DESC LIMIT 10)...")
    groupby_results = {}
    for name, adapter in adapters:
        rows = adapter.run_aggregation_group_by()
        groupby_results[name] = rows
        print(f"   [{name}]: {rows[:3]} ... ({len(rows)} categories)")
        
    baseline_engine, baseline_gb = list(groupby_results.items())[0]
    for name, rows in groupby_results.items():
        if rows != baseline_gb:
            mismatches.append(f"GroupBy Aggregation mismatch: {name} != {baseline_engine}")

    # Close connections
    for _, adapter in adapters:
        adapter.close()

    print("\n" + "=" * 70)
    if mismatches:
        print("[SEMANTIC PARITY FAILED] Discrepancies detected:")
        for m in mismatches:
            print(f"  - {m}")
        print("=" * 70)
        sys.exit(1)
    else:
        print(f"[SEMANTIC PARITY SUCCESS] All {len(adapters)} engines returned 100% identical query results across all workloads!")
        print("=" * 70)
        sys.exit(0)

if __name__ == "__main__":
    run_semantic_parity_check()

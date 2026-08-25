"""
Master Benchmark Orchestration Pipeline.
Executes end-to-end benchmark suite across CognoDB Cloud and local competitor databases (Memgraph, FalkorDB, KùzuDB, Apache AGE)
under strict hardware parity (0.5 vCPU, 256 MB RAM, 1 GB Storage).
Supports multi-run repetitions (default: 3), raw run archiving, median statistical aggregation,
variance computation, deterministic seed saving, and strict deliverable validation.
"""

import os
import sys
import json
import csv
import argparse
import random
import numpy as np
from typing import List, Dict, Tuple, Any
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from data.download_dataset import process_public_graph, NODES_CSV, RELS_CSV
from src.harness.base import BaseGraphAdapter
from src.harness.stats import BenchmarkMetrics, LatencyDistribution, IngestMetrics, ConcurrencyMetrics, ResourceFootprint
from src.engines.cognodb import CognoDBAdapter
from src.engines.age_adapter import ApacheAGEAdapter
from src.engines.memgraph_adapter import MemgraphAdapter
from src.engines.falkordb_adapter import FalkorDBAdapter
from src.engines.kuzu_adapter import KuzuAdapter
from src.workloads.ingest import run_ingest_benchmark
from src.workloads.traversals import run_traversals_benchmark
from src.workloads.lookups import run_lookups_benchmark
from src.workloads.aggregations import run_aggregations_benchmark
from src.workloads.mixed_concurrency import run_mixed_concurrency_benchmark
from src.visualizer import generate_all_charts
from scripts.validate_results import validate_results_file
from scripts.generate_markdown_tables import generate_markdown_tables
from scripts.audit_docker_resources import audit_containers
from scripts.audit_environment import audit_full_environment
from scripts.measure_rtt import run_rtt_audit

load_dotenv()

def parse_args():
    parser = argparse.ArgumentParser(description="Graph Database Benchmark Suite")
    parser.add_argument("--traversal-iterations", type=int, default=100, help="Number of measured traversal queries (default: 100)")
    parser.add_argument("--lookup-iterations", type=int, default=100, help="Number of measured lookup queries (default: 100)")
    parser.add_argument("--aggregation-iterations", type=int, default=100, help="Number of measured aggregation queries (default: 100)")
    parser.add_argument("--concurrency-duration", type=float, default=10.0, help="Duration (sec) per concurrency sweep (default: 10.0)")
    parser.add_argument("--repetitions", type=int, default=3, help="Number of full benchmark repetitions (default: 3)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic queries (default: 42)")
    parser.add_argument("--skip-cognodb", action="store_true", help="Skip CognoDB Cloud run if credentials are not configured")
    parser.add_argument("--results-dir", type=str, default=os.path.join(BASE_DIR, "results"))
    return parser.parse_args()

def load_immutable_dataset(nodes_file: str, rels_file: str) -> Tuple[List[Dict[str, Any]], List[Tuple[int, int, str, int]]]:
    if not os.path.exists(nodes_file) or not os.path.exists(rels_file):
        print("Dataset not found. Generating immutable SNAP dataset...")
        process_public_graph()

    nodes = []
    with open(nodes_file, "r", encoding="utf-8") as f:
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
    with open(rels_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            relationships.append((
                int(row["src_id"]),
                int(row["dst_id"]),
                row["type"],
                int(row["weight"])
            ))

    return nodes, relationships

def run_suite_for_adapter(adapter: BaseGraphAdapter, nodes: List[Dict[str, Any]], relationships: List[Tuple[int, int, str, int]], args) -> BenchmarkMetrics:
    print(f"\n{'='*70}\nSTARTING BENCHMARK WORKLOAD: {adapter.name}\n{'='*70}")
    metrics = BenchmarkMetrics(database_name=adapter.name)

    node_ids = [n["id"] for n in nodes]
    categories = list(set([n["category"] for n in nodes]))

    try:
        adapter.connect()
    except Exception as e:
        print(f"FAILED to connect to {adapter.name}: {e}")
        metrics.status = "FAILED"
        metrics.caveats.append(f"Connection failed: {str(e)}")
        return metrics

    try:
        # 1. Ingestion
        metrics.ingest = run_ingest_benchmark(adapter, nodes, relationships)

        # 2. Traversals (>= 100 measured iterations)
        d1, d2, d3 = run_traversals_benchmark(
            adapter,
            node_ids,
            warmup_iterations=15,
            measured_iterations=args.traversal_iterations,
            seed=args.seed
        )
        metrics.traversal_1hop = d1
        metrics.traversal_2hop = d2
        metrics.traversal_3hop = d3

        # 3. Lookups (>= 100 measured iterations)
        point_dist, idx_dist = run_lookups_benchmark(
            adapter,
            node_ids,
            categories,
            warmup_iterations=15,
            measured_iterations=args.lookup_iterations,
            seed=args.seed
        )
        metrics.point_lookup = point_dist
        metrics.indexed_lookup = idx_dist

        # 4. Aggregations (>= 100 measured iterations, reporting p50 and p95)
        count_dist, grp_dist = run_aggregations_benchmark(
            adapter,
            warmup_iterations=10,
            measured_iterations=args.aggregation_iterations
        )
        metrics.aggregation_count = count_dist
        metrics.aggregation_groupby = grp_dist

        # 5. Mixed Concurrency (1, 10, 40 workers)
        conc_results = run_mixed_concurrency_benchmark(
            adapter,
            node_ids,
            concurrency_levels=[1, 10, 40],
            duration_per_level_sec=args.concurrency_duration
        )
        metrics.concurrency_1 = conc_results.get(1)
        metrics.concurrency_10 = conc_results.get(10)
        metrics.concurrency_40 = conc_results.get(40)

        # 6. Footprint
        footprint_info = adapter.get_resource_footprint()
        metrics.footprint.memory_mb = str(footprint_info.get("memory_mb", "not observable"))
        metrics.footprint.disk_storage_mb = str(footprint_info.get("disk_storage_mb", "not observable"))
        metrics.footprint.instance_specs = str(footprint_info.get("instance_specs", "0.5 vCPU, 256 MB RAM"))
        metrics.status = "SUCCESS"

    except Exception as e:
        print(f"Error during benchmark run on {adapter.name}: {e}")
        metrics.status = "FAILED"
        metrics.caveats.append(f"Workload error: {str(e)}")
    finally:
        try:
            adapter.close()
        except Exception:
            pass

    return metrics

def aggregate_repetitions(runs_data: List[Dict[str, Any]], engines: List[str]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Computes median across repetitions for the headline metrics.json,
    and calculates statistical variance (min, max, median, mean, std, CV%) for variance.csv.
    """
    aggregated_engines = {}
    variance_rows = []

    for eng in engines:
        eng_runs = [r[eng] for r in runs_data if eng in r and r[eng].get("status") == "SUCCESS"]
        if not eng_runs:
            # If all failed or absent, copy last available state
            last_run = [r[eng] for r in runs_data if eng in r][-1]
            aggregated_engines[eng] = last_run
            continue

        base_metrics = eng_runs[0]
        agg_metrics = {
            "database_name": eng,
            "status": "SUCCESS",
            "caveats": [],
            "metrics": {}
        }

        # List of numeric paths to aggregate
        metric_paths = [
            ("ingest.nodes_per_sec", "Ingest Nodes/sec", "rate"),
            ("ingest.rels_per_sec", "Ingest Rels/sec", "rate"),
            ("ingest.node_load_time_sec", "Ingest Node Time (s)", "time"),
            ("ingest.rel_load_time_sec", "Ingest Rel Time (s)", "time"),
            ("ingest.total_wall_clock_sec", "Ingest Wall Clock (s)", "time"),
            ("traversal_1hop.cold_ms", "1-Hop Cold Latency (ms)", "latency"),
            ("traversal_1hop.p50_ms", "1-Hop p50 (ms)", "latency"),
            ("traversal_1hop.p95_ms", "1-Hop p95 (ms)", "latency"),
            ("traversal_2hop.cold_ms", "2-Hop Cold Latency (ms)", "latency"),
            ("traversal_2hop.p50_ms", "2-Hop p50 (ms)", "latency"),
            ("traversal_2hop.p95_ms", "2-Hop p95 (ms)", "latency"),
            ("traversal_3hop.cold_ms", "3-Hop Cold Latency (ms)", "latency"),
            ("traversal_3hop.p50_ms", "3-Hop p50 (ms)", "latency"),
            ("traversal_3hop.p95_ms", "3-Hop p95 (ms)", "latency"),
            ("point_lookup.p50_ms", "Point Lookup p50 (ms)", "latency"),
            ("point_lookup.p95_ms", "Point Lookup p95 (ms)", "latency"),
            ("indexed_lookup.p50_ms", "Indexed Lookup p50 (ms)", "latency"),
            ("indexed_lookup.p95_ms", "Indexed Lookup p95 (ms)", "latency"),
            ("aggregation_count.p50_ms", "Count Agg p50 (ms)", "latency"),
            ("aggregation_count.p95_ms", "Count Agg p95 (ms)", "latency"),
            ("aggregation_groupby.p50_ms", "GroupBy Agg p50 (ms)", "latency"),
            ("aggregation_groupby.p95_ms", "GroupBy Agg p95 (ms)", "latency"),
            ("concurrency_1.qps", "Concurrency 1 QPS", "qps"),
            ("concurrency_1.p50_ms", "Concurrency 1 p50 (ms)", "latency"),
            ("concurrency_1.p95_ms", "Concurrency 1 p95 (ms)", "latency"),
            ("concurrency_10.qps", "Concurrency 10 QPS", "qps"),
            ("concurrency_10.p50_ms", "Concurrency 10 p50 (ms)", "latency"),
            ("concurrency_10.p95_ms", "Concurrency 10 p95 (ms)", "latency"),
            ("concurrency_40.qps", "Concurrency 40 QPS", "qps"),
            ("concurrency_40.p50_ms", "Concurrency 40 p50 (ms)", "latency"),
            ("concurrency_40.p95_ms", "Concurrency 40 p95 (ms)", "latency")
        ]

        def get_val(run_dict, path):
            parts = path.split(".")
            curr = run_dict.get("metrics", {})
            for p in parts:
                if isinstance(curr, dict):
                    curr = curr.get(p)
                else:
                    return 0.0
            return float(curr) if curr is not None else 0.0

        def set_val(target_dict, path, val):
            parts = path.split(".")
            curr = target_dict.setdefault("metrics", {})
            for p in parts[:-1]:
                curr = curr.setdefault(p, {})
            curr[parts[-1]] = val

        # Initialize full structure from first run
        import copy
        agg_metrics["metrics"] = copy.deepcopy(eng_runs[0]["metrics"])

        for path, display_name, mtype in metric_paths:
            vals = [get_val(r, path) for r in eng_runs]
            arr = np.array(vals, dtype=np.float64)
            med = float(np.median(arr))
            mean = float(np.mean(arr))
            std = float(np.std(arr))
            v_min = float(np.min(arr))
            v_max = float(np.max(arr))
            cv_pct = (std / mean * 100.0) if mean > 0 else 0.0

            # Set median in aggregated metrics
            digits = 3 if mtype in ["latency", "time"] else 2
            set_val(agg_metrics, path, round(med, digits))

            # Store variance row
            run_cols = {f"run_{i+1:02d}": round(vals[i], digits) for i in range(len(vals))}
            variance_rows.append({
                "database": eng,
                "metric": display_name,
                **run_cols,
                "median": round(med, digits),
                "min": round(v_min, digits),
                "max": round(v_max, digits),
                "mean": round(mean, digits),
                "std_dev": round(std, digits),
                "cv_pct": round(cv_pct, 2)
            })

        aggregated_engines[eng] = agg_metrics

    return aggregated_engines, variance_rows

def main():
    args = parse_args()
    os.makedirs(args.results_dir, exist_ok=True)
    raw_dir = os.path.join(args.results_dir, "raw")
    os.makedirs(raw_dir, exist_ok=True)
    charts_dir = os.path.join(args.results_dir, "charts")
    os.makedirs(charts_dir, exist_ok=True)

    print("Loading official SNAP cit-HepPh Citation Graph Dataset...")
    nodes, relationships = load_immutable_dataset(NODES_CSV, RELS_CSV)
    print(f"Verified immutable dataset: {len(nodes):,} nodes and {len(relationships):,} relationships loaded into memory.")

    # Save deterministic query seeds
    random.seed(args.seed)
    all_node_ids = [n["id"] for n in nodes]
    query_seeds = {
        "random_seed": args.seed,
        "traversal_start_node_ids": random.sample(all_node_ids, k=min(200, len(all_node_ids))),
        "point_lookup_node_ids": random.sample(all_node_ids, k=min(200, len(all_node_ids))),
        "indexed_lookup_categories": sorted(list(set(n["category"] for n in nodes)))
    }
    seeds_path = os.path.join(args.results_dir, "query_seeds.json")
    with open(seeds_path, "w", encoding="utf-8") as f:
        json.dump(query_seeds, f, indent=2)

    adapters: List[BaseGraphAdapter] = []

    # 1. CognoDB Cloud
    if not args.skip_cognodb:
        cog_uri = os.getenv("COGNODB_URI", "")
        cog_pwd = os.getenv("COGNODB_PASSWORD", "")
        if cog_uri and cog_pwd:
            adapters.append(CognoDBAdapter())
        else:
            print("\n[NOTE] CognoDB Cloud credentials not fully configured in .env.")
            print("To include CognoDB Cloud, set COGNODB_URI and COGNODB_PASSWORD in .env.")

    # 2. Memgraph (Docker 0.5 CPU / 256MB)
    adapters.append(MemgraphAdapter())

    # 3. FalkorDB (Docker 0.5 CPU / 256MB)
    adapters.append(FalkorDBAdapter())

    # 4. KùzuDB (Containerized 0.5 CPU / 256MB)
    adapters.append(KuzuAdapter())

    # 5. Apache AGE (Docker 0.5 CPU / 256MB)
    adapters.append(ApacheAGEAdapter())

    runs_data = []
    engine_names = [a.name for a in adapters]

    for rep in range(1, args.repetitions + 1):
        run_folder = os.path.join(raw_dir, f"run_{rep:02d}")
        os.makedirs(run_folder, exist_ok=True)
        print(f"\n{'#'*70}\nSTARTING BENCHMARK REPETITION {rep}/{args.repetitions}\n{'#'*70}")
        
        rep_engines_dict = {}
        for adapter in adapters:
            res = run_suite_for_adapter(adapter, nodes, relationships, args)
            rep_engines_dict[adapter.name] = res.to_dict()

        runs_data.append(rep_engines_dict)

        # Write individual raw run metrics
        run_metrics_path = os.path.join(run_folder, "metrics.json")
        with open(run_metrics_path, "w", encoding="utf-8") as f:
            json.dump({
                "metadata": {
                    "dataset": "Stanford SNAP cit-HepPh (18,317 nodes, 125,000 edges)",
                    "hardware_constraint": "0.5 vCPU, 256 MB RAM, 1 GB Storage",
                    "repetition_index": rep,
                    "total_repetitions": args.repetitions,
                    "traversal_iterations": args.traversal_iterations,
                    "lookup_iterations": args.lookup_iterations,
                    "aggregation_iterations": args.aggregation_iterations,
                    "concurrency_duration_sec": args.concurrency_duration
                },
                "engines": rep_engines_dict
            }, f, indent=2)

    # Statistical Aggregation (Median headline + Variance reporting)
    print(f"\nAggregating results across {args.repetitions} repetitions (Median headline values)...")
    aggregated_engines, variance_rows = aggregate_repetitions(runs_data, engine_names)

    # Save aggregated metrics.json
    results_path = os.path.join(args.results_dir, "metrics.json")
    full_output = {
        "metadata": {
            "dataset": "Stanford SNAP cit-HepPh (18,317 nodes, 125,000 edges)",
            "hardware_constraint": "0.5 vCPU, 256 MB RAM, 1 GB Storage",
            "repetitions_count": args.repetitions,
            "aggregation_method": "Median of runs for headline metrics; min/max/std/CV for variance analysis",
            "traversal_iterations": args.traversal_iterations,
            "lookup_iterations": args.lookup_iterations,
            "aggregation_iterations": args.aggregation_iterations,
            "concurrency_duration_sec": args.concurrency_duration
        },
        "engines": aggregated_engines
    }

    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(full_output, f, indent=2)
    print(f"Aggregated metrics written to {results_path}")

    # Write variance.csv
    if variance_rows:
        variance_path = os.path.join(args.results_dir, "variance.csv")
        fieldnames = ["database", "metric"] + [f"run_{i+1:02d}" for i in range(args.repetitions)] + ["median", "min", "max", "mean", "std_dev", "cv_pct"]
        with open(variance_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(variance_rows)
        print(f"Statistical variance report written to {variance_path}")

    # Audits
    audit_containers()
    audit_full_environment()
    run_rtt_audit()

    # Generate charts
    generate_all_charts(results_path, charts_dir)

    # Sync README and REPORT markdown tables
    generate_markdown_tables(results_path, sync_files=True)

    # Strict Deliverable Validation
    summary_path = os.path.join(args.results_dir, "summary.csv")
    validate_results_file(results_path, summary_path, allow_incomplete_for_dev=args.skip_cognodb)

    print("\nBenchmark Suite Execution & Synchronization Complete!")

if __name__ == "__main__":
    main()

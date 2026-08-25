"""
Rigorous Validation Script for Graph Database Benchmark Deliverables.
Enforces:
1. Presence of all 5 required engines (CognoDB Cloud, Memgraph, FalkorDB, KùzuDB, Apache AGE).
2. Status == SUCCESS with complete measurements for each engine.
3. Completeness of all metrics (ingestion, 1/2/3-hop traversals, lookups, aggregations, concurrency 1/10/40, footprint).
4. Mathematical consistency and statistical invariants (p95 >= p50, finite floats, valid throughput rates).
5. Exits with sys.exit(1) on ANY failure, incomplete metric, or missing engine in strict mode.
"""

import os
import sys
import json
import csv
import math
from typing import Dict, Any, List

EXPECTED_ENGINES = [
    "CognoDB Cloud",
    "Memgraph",
    "FalkorDB",
    "KùzuDB",
    "Apache AGE"
]

def assert_finite_positive(val: Any, name: str, db: str, allow_zero: bool = False) -> float:
    if val is None or not isinstance(val, (int, float)):
        raise ValueError(f"[{db}] Metric '{name}' is missing or not a number: {val}")
    if not math.isfinite(val):
        raise ValueError(f"[{db}] Metric '{name}' is not finite: {val}")
    if not allow_zero and val <= 0:
        raise ValueError(f"[{db}] Metric '{name}' must be positive: {val}")
    if allow_zero and val < 0:
        raise ValueError(f"[{db}] Metric '{name}' cannot be negative: {val}")
    return float(val)

def validate_results_file(metrics_path: str, summary_csv_path: str, allow_incomplete_for_dev: bool = False) -> bool:
    if not os.path.exists(metrics_path):
        print(f"[FATAL] Metrics file does not exist: {metrics_path}")
        return False

    with open(metrics_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except Exception as e:
            print(f"[FATAL] Invalid JSON in {metrics_path}: {e}")
            return False

    engines_data = data.get("engines", {})
    errors: List[str] = []
    summary_rows: List[Dict[str, Any]] = []

    print("=" * 70)
    print(f"STRICT AUDIT VALIDATION: Validating {len(engines_data)} Engine Reports...")
    print("=" * 70)

    # 1. Engine Presence Verification
    found_engines = set(engines_data.keys())
    for expected in EXPECTED_ENGINES:
        if expected not in found_engines:
            msg = f"Missing required engine: '{expected}'"
            if allow_incomplete_for_dev:
                print(f"[DEV WARNING] {msg}")
            else:
                errors.append(msg)

    if len(found_engines) > len(EXPECTED_ENGINES):
        errors.append(f"Unexpected extra engines present: {found_engines - set(EXPECTED_ENGINES)}")

    for db_name, report in engines_data.items():
        print(f"\nVerifying engine: [{db_name}]")
        status = report.get("status")
        if status != "SUCCESS":
            msg = f"[{db_name}] Status is '{status}', expected 'SUCCESS'. Caveats: {report.get('caveats')}"
            if allow_incomplete_for_dev:
                print(f"[DEV WARNING] {msg}")
            else:
                errors.append(msg)
            continue

        m = report.get("metrics", {})
        if not m:
            errors.append(f"[{db_name}] No 'metrics' object found.")
            continue

        try:
            # 2. Ingest Metrics Validation
            ingest = m.get("ingest")
            if not ingest:
                raise ValueError(f"[{db_name}] Missing 'ingest' metrics")
            
            nodes_sec = assert_finite_positive(ingest.get("nodes_per_sec"), "nodes_per_sec", db_name)
            rels_sec = assert_finite_positive(ingest.get("rels_per_sec"), "rels_per_sec", db_name)
            t_node = assert_finite_positive(ingest.get("node_load_time_sec"), "node_load_time_sec", db_name)
            t_rel = assert_finite_positive(ingest.get("rel_load_time_sec"), "rel_load_time_sec", db_name)
            t_setup = assert_finite_positive(ingest.get("setup_time_sec"), "setup_time_sec", db_name, allow_zero=True)
            t_wall = assert_finite_positive(ingest.get("total_wall_clock_sec"), "total_wall_clock_sec", db_name)
            
            # Mathematical consistency (allow statistical median variance across stages)
            t_sum = t_setup + t_node + t_rel
            if abs(t_wall - t_sum) > 5.0 and abs(t_wall - t_sum) / max(t_wall, 1.0) > 0.25:
                errors.append(f"[{db_name}] Ingest timer mismatch: wall_clock ({t_wall}s) != sum of stages ({t_sum}s)")

            # 3. Traversal Metrics Validation (1, 2, 3 hops)
            for hop in ["1hop", "2hop", "3hop"]:
                hop_m = m.get(f"traversal_{hop}")
                if not hop_m:
                    raise ValueError(f"[{db_name}] Missing 'traversal_{hop}' metrics")
                p50 = assert_finite_positive(hop_m.get("p50_ms"), f"traversal_{hop}.p50_ms", db_name)
                p95 = assert_finite_positive(hop_m.get("p95_ms"), f"traversal_{hop}.p95_ms", db_name)
                cold = assert_finite_positive(hop_m.get("cold_ms"), f"traversal_{hop}.cold_ms", db_name)
                if p95 < p50:
                    errors.append(f"[{db_name}] Statistical anomaly: traversal_{hop} p95 ({p95}ms) < p50 ({p50}ms)")

            # 4. Lookup Metrics Validation
            for lk in ["point_lookup", "indexed_lookup"]:
                lk_m = m.get(lk)
                if not lk_m:
                    raise ValueError(f"[{db_name}] Missing '{lk}' metrics")
                p50 = assert_finite_positive(lk_m.get("p50_ms"), f"{lk}.p50_ms", db_name)
                p95 = assert_finite_positive(lk_m.get("p95_ms"), f"{lk}.p95_ms", db_name)
                if p95 < p50:
                    errors.append(f"[{db_name}] Statistical anomaly: {lk} p95 ({p95}ms) < p50 ({p50}ms)")

            # 5. Aggregation Metrics Validation
            for agg in ["aggregation_count", "aggregation_groupby"]:
                agg_m = m.get(agg)
                if not agg_m:
                    raise ValueError(f"[{db_name}] Missing '{agg}' metrics")
                p50 = assert_finite_positive(agg_m.get("p50_ms"), f"{agg}.p50_ms", db_name)
                p95 = assert_finite_positive(agg_m.get("p95_ms"), f"{agg}.p95_ms", db_name)
                if p95 < p50:
                    errors.append(f"[{db_name}] Statistical anomaly: {agg} p95 ({p95}ms) < p50 ({p50}ms)")

            # 6. Concurrency Metrics Validation (1, 10, 40)
            for conc in [1, 10, 40]:
                conc_m = m.get(f"concurrency_{conc}")
                if not conc_m:
                    raise ValueError(f"[{db_name}] Missing 'concurrency_{conc}' metrics")
                qps = assert_finite_positive(conc_m.get("qps"), f"concurrency_{conc}.qps", db_name)
                p95 = assert_finite_positive(conc_m.get("p95_ms"), f"concurrency_{conc}.p95_ms", db_name)
                errs = assert_finite_positive(conc_m.get("error_count"), f"concurrency_{conc}.error_count", db_name, allow_zero=True)

            # 7. Footprint Validation
            footprint = m.get("footprint", {})
            if not footprint or "instance_specs" not in footprint:
                errors.append(f"[{db_name}] Missing resource footprint declaration")

            # Collect summary row
            summary_rows.append({
                "database": db_name,
                "status": status,
                "node_ingest_rate": nodes_sec,
                "rel_ingest_rate": rels_sec,
                "total_wall_clock_sec": t_wall,
                "hop1_p50_ms": m["traversal_1hop"]["p50_ms"],
                "hop1_p95_ms": m["traversal_1hop"]["p95_ms"],
                "hop2_p50_ms": m["traversal_2hop"]["p50_ms"],
                "hop2_p95_ms": m["traversal_2hop"]["p95_ms"],
                "hop3_p50_ms": m["traversal_3hop"]["p50_ms"],
                "hop3_p95_ms": m["traversal_3hop"]["p95_ms"],
                "point_p50_ms": m["point_lookup"]["p50_ms"],
                "point_p95_ms": m["point_lookup"]["p95_ms"],
                "indexed_p50_ms": m["indexed_lookup"]["p50_ms"],
                "indexed_p95_ms": m["indexed_lookup"]["p95_ms"],
                "count_agg_p50_ms": m["aggregation_count"]["p50_ms"],
                "count_agg_p95_ms": m["aggregation_count"]["p95_ms"],
                "groupby_p50_ms": m["aggregation_groupby"]["p50_ms"],
                "groupby_p95_ms": m["aggregation_groupby"]["p95_ms"],
                "concurrency_1_qps": m["concurrency_1"]["qps"],
                "concurrency_10_qps": m["concurrency_10"]["qps"],
                "concurrency_40_qps": m["concurrency_40"]["qps"],
                "concurrency_40_errors": m["concurrency_40"]["error_count"]
            })

            print(f"  -> [OK] All metrics and invariants verified for {db_name}")

        except Exception as e:
            errors.append(f"[{db_name}] Validation exception: {str(e)}")

    if summary_rows:
        with open(summary_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
            writer.writeheader()
            writer.writerows(summary_rows)
        print(f"\nWrote verified summary to {summary_csv_path}")

    if errors:
        print("\n" + "!" * 70)
        print(f"[VALIDATION FAILED] Found {len(errors)} blocker errors:")
        for err in errors:
            print(f"  - {err}")
        print("!" * 70)
        return False

    print("\n" + "=" * 70)
    print("[AUDIT SUCCESS] 100% of required engines and metrics passed strict verification!")
    print("=" * 70)
    return True

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    metrics_file = os.path.join(base_dir, "results", "metrics.json")
    summary_file = os.path.join(base_dir, "results", "summary.csv")
    allow_incomplete = "--allow-dev" in sys.argv
    success = validate_results_file(metrics_file, summary_file, allow_incomplete_for_dev=allow_incomplete)
    sys.exit(0 if success else 1)

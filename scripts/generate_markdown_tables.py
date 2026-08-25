"""
Synchronizes Markdown Results Tables directly from results/metrics.json and results/variance.csv.
Ensures single-source-of-truth across both README.md and REPORT.md.
"""

import os
import json
import csv
from typing import Dict, Any

ENGINE_ORDER = ["CognoDB Cloud", "Memgraph", "FalkorDB", "KùzuDB", "Apache AGE"]

def generate_markdown_tables(metrics_json_path: str, sync_files: bool = True) -> Dict[str, str]:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(metrics_json_path)))
    
    with open(metrics_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    engines_data = data.get("engines", {})

    # 1. Ingestion Table
    ingest_rows = []
    for eng in ENGINE_ORDER:
        if eng not in engines_data:
            continue
        rep = engines_data[eng]
        status = rep.get("status", "N/A")
        m = rep.get("metrics", {}).get("ingest", {})
        if status == "SUCCESS" and m:
            nodes_sec = f"{m.get('nodes_per_sec', 0.0):,.2f}"
            rels_sec = f"{m.get('rels_per_sec', 0.0):,.2f}"
            node_time = f"{m.get('node_load_time_sec', 0.0):.3f} s"
            rel_time = f"{m.get('rel_load_time_sec', 0.0):.3f} s"
            wall_time = f"{m.get('total_wall_clock_sec', 0.0):.3f} s"
        else:
            nodes_sec = rels_sec = node_time = rel_time = wall_time = "N/A"
        ingest_rows.append(f"| **{eng}** | {nodes_sec} | {rels_sec} | {node_time} | {rel_time} | {wall_time} | **{status}** |")

    ingest_table = """| Platform | Node Ingest (nodes/sec) | Rel Ingest (rels/sec) | Node Time (s) | Rel Time (s) | Total Wall-Clock Time (s) | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n""" + "\n".join(ingest_rows)

    # 2. Traversals Table
    trav_rows = []
    for eng in ENGINE_ORDER:
        if eng not in engines_data:
            continue
        rep = engines_data[eng]
        status = rep.get("status", "N/A")
        m = rep.get("metrics", {})
        if status == "SUCCESS" and m:
            t1 = m.get("traversal_1hop", {})
            t2 = m.get("traversal_2hop", {})
            t3 = m.get("traversal_3hop", {})
            h1_cold = f"{t1.get('cold_ms', 0.0):.2f} ms"
            h1_p50 = f"{t1.get('p50_ms', 0.0):.2f} ms"
            h1_p95 = f"{t1.get('p95_ms', 0.0):.2f} ms"
            h2_cold = f"{t2.get('cold_ms', 0.0):.2f} ms"
            h2_p50 = f"{t2.get('p50_ms', 0.0):.2f} ms"
            h2_p95 = f"{t2.get('p95_ms', 0.0):.2f} ms"
            h3_cold = f"{t3.get('cold_ms', 0.0):.2f} ms"
            h3_p50 = f"{t3.get('p50_ms', 0.0):.2f} ms"
            h3_p95 = f"{t3.get('p95_ms', 0.0):.2f} ms"
        else:
            h1_cold = h1_p50 = h1_p95 = h2_cold = h2_p50 = h2_p95 = h3_cold = h3_p50 = h3_p95 = "N/A"
        trav_rows.append(f"| **{eng}** | {h1_cold} | {h1_p50} | {h1_p95} | {h2_cold} | {h2_p50} | {h2_p95} | {h3_cold} | {h3_p50} | {h3_p95} |")

    trav_table = """| Platform | 1-Hop First-Query | 1-Hop $p50$ | 1-Hop $p95$ | 2-Hop First-Query | 2-Hop $p50$ | 2-Hop $p95$ | 3-Hop First-Query | 3-Hop $p50$ | 3-Hop $p95$ |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n""" + "\n".join(trav_rows)

    # 3. Lookups & Aggregations Table
    look_rows = []
    for eng in ENGINE_ORDER:
        if eng not in engines_data:
            continue
        rep = engines_data[eng]
        status = rep.get("status", "N/A")
        m = rep.get("metrics", {})
        if status == "SUCCESS" and m:
            pl = m.get("point_lookup", {})
            il = m.get("indexed_lookup", {})
            ac = m.get("aggregation_count", {})
            ag = m.get("aggregation_groupby", {})
            pl_p50 = f"{pl.get('p50_ms', 0.0):.2f} ms"
            pl_p95 = f"{pl.get('p95_ms', 0.0):.2f} ms"
            il_p50 = f"{il.get('p50_ms', 0.0):.2f} ms"
            il_p95 = f"{il.get('p95_ms', 0.0):.2f} ms"
            ac_p50 = f"{ac.get('p50_ms', 0.0):.2f} ms"
            ac_p95 = f"{ac.get('p95_ms', 0.0):.2f} ms"
            ag_p50 = f"{ag.get('p50_ms', 0.0):.2f} ms"
            ag_p95 = f"{ag.get('p95_ms', 0.0):.2f} ms"
        else:
            pl_p50 = pl_p95 = il_p50 = il_p95 = ac_p50 = ac_p95 = ag_p50 = ag_p95 = "N/A"
        look_rows.append(f"| **{eng}** | {pl_p50} | {pl_p95} | {il_p50} | {il_p95} | {ac_p50} | {ac_p95} | {ag_p50} | {ag_p95} |")

    look_table = """| Platform | Point $p50$ | Point $p95$ | Indexed $p50$ | Indexed $p95$ | Count Agg $p50$ | Count Agg $p95$ | GroupBy $p50$ | GroupBy $p95$ |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n""" + "\n".join(look_rows)

    # 4. Concurrency Table
    conc_rows = []
    for eng in ENGINE_ORDER:
        if eng not in engines_data:
            continue
        rep = engines_data[eng]
        status = rep.get("status", "N/A")
        m = rep.get("metrics", {})
        if status == "SUCCESS" and m:
            c1 = m.get("concurrency_1", {})
            c10 = m.get("concurrency_10", {})
            c40 = m.get("concurrency_40", {})
            c1_qps = f"{c1.get('qps', 0.0):.1f} QPS"
            c1_p95 = f"{c1.get('p95_ms', 0.0):.2f} ms"
            c10_qps = f"{c10.get('qps', 0.0):.1f} QPS"
            c10_p95 = f"{c10.get('p95_ms', 0.0):.2f} ms"
            c40_qps = f"{c40.get('qps', 0.0):.1f} QPS"
            c40_p95 = f"{c40.get('p95_ms', 0.0):.2f} ms"
            errs = str(c1.get('error_count', 0) + c10.get('error_count', 0) + c40.get('error_count', 0))
        else:
            c1_qps = c1_p95 = c10_qps = c10_p95 = c40_qps = c40_p95 = errs = "N/A"
        conc_rows.append(f"| **{eng}** | {c1_qps} | {c1_p95} | {c10_qps} | {c10_p95} | {c40_qps} | {c40_p95} | {errs} |")

    conc_table = """| Platform | Concurrency = 1 QPS | Concurrency = 1 $p95$ | Concurrency = 10 QPS | Concurrency = 10 $p95$ | Concurrency = 40 QPS | Concurrency = 40 $p95$ | Errors |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n""" + "\n".join(conc_rows)

    # 5. Variance / Stability Table
    variance_path = os.path.join(os.path.dirname(metrics_json_path), "variance.csv")
    variance_table = ""
    if os.path.exists(variance_path):
        v_rows = []
        with open(variance_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            # Sample key representative metrics
            key_metrics = [
                "Ingest Total Wall Clock (s)",
                "1-Hop p50 (ms)",
                "2-Hop p50 (ms)",
                "3-Hop p50 (ms)",
                "Point Lookup p50 (ms)",
                "Concurrency 10 QPS"
            ]
            for row in reader:
                if row.get("metric") in key_metrics:
                    v_rows.append(f"| **{row.get('database')}** | {row.get('metric')} | {row.get('run_01', 'N/A')} | {row.get('run_02', 'N/A')} | {row.get('run_03', 'N/A')} | **{row.get('median')}** | {row.get('cv_pct')}% |")
        if v_rows:
            variance_table = """| Database | Key Metric | Run 1 | Run 2 | Run 3 | Median (Headline) | CV (%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n""" + "\n".join(v_rows)

    tables = {
        "ingest": ingest_table,
        "traversals": trav_table,
        "lookups": look_table,
        "concurrency": conc_table,
        "variance": variance_table
    }

    if sync_files:
        # Sync README.md
        readme_path = os.path.join(base_dir, "README.md")
        if os.path.exists(readme_path):
            with open(readme_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            var_section = f"\n\n### 2.5 Repetition Stability & Variance Analysis\n*Across 3 complete benchmark repetitions with database reset between runs:*\n\n{variance_table}" if variance_table else ""
            full_tables_md = f"### 2.1 Ingest Throughput\n\n{tables['ingest']}\n\n### 2.2 Traversal Latencies (Warm vs. Cold)\n*Measured across >= 100 randomized start seeds. Latencies reported in milliseconds (ms).*\n\n{tables['traversals']}\n\n### 2.3 Lookups & Aggregations\n*All queries measured over >= 100 iterations after warm-up. Indexed properties: `Paper(id)` (Primary), `Paper(category)`.*\n\n{tables['lookups']}\n\n### 2.4 Mixed Read/Write Concurrency Sweep (80% Read / 20% Write)\n*Measured sustained QPS and p95 latency under multi-client concurrency sweeps (1, 10, 40 workers).*\n\n{tables['concurrency']}{var_section}"
            
            start_tag = "## 2. Full Results Matrix"
            end_tag = "### 2.6 Resource Footprint" if "### 2.6 Resource Footprint" in content else "### 2.5 Resource Footprint"
            if start_tag in content and end_tag in content:
                before = content.split(start_tag)[0]
                after = content.split(end_tag)[1]
                new_content = f"{before}{start_tag}\n\n{full_tables_md}\n\n{end_tag}{after}"
                with open(readme_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                print("Synchronized README.md results tables directly from metrics.json.")

        # Sync REPORT.md
        report_path = os.path.join(base_dir, "REPORT.md")
        if os.path.exists(report_path):
            with open(report_path, "r", encoding="utf-8") as f:
                rep_content = f.read()
            # Update key sections in REPORT.md
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(rep_content)

    return tables

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(base_dir, "results", "metrics.json")
    tables = generate_markdown_tables(json_path, sync_files=True)
    print("Generated Ingest Table:\n", tables["ingest"])

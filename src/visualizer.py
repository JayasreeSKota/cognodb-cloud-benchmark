"""
Visualization generator for graph database benchmarks.
Reads directly from results/metrics.json to generate high-resolution comparison charts.
Enforces consistent color palettes and explicit N/A rendering across all 5 engines.
"""

import os
import json
from typing import Dict, Any, List
import matplotlib.pyplot as plt
import numpy as np

ENGINE_ORDER = ["CognoDB Cloud", "Memgraph", "FalkorDB", "KùzuDB", "Apache AGE"]

ENGINE_COLORS = {
    "CognoDB Cloud": "#2563EB",  # Royal Blue
    "Memgraph": "#0D9488",      # Teal
    "FalkorDB": "#EA580C",      # Vibrant Orange
    "KùzuDB": "#7C3AED",        # Purple
    "Apache AGE": "#D97706"     # Amber / Gold
}

def setup_plot_style():
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    plt.rcParams.update({
        'font.size': 11,
        'axes.labelsize': 12,
        'axes.titlesize': 13,
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'legend.fontsize': 10,
        'figure.titlesize': 14,
        'figure.dpi': 300,
        'savefig.dpi': 300,
        'savefig.bbox': 'tight'
    })

def plot_ingest_throughput(metrics: Dict[str, Any], output_dir: str):
    setup_plot_style()
    engines = [e for e in ENGINE_ORDER if e in metrics]
    if not engines:
        return

    node_rates = []
    rel_rates = []
    colors = [ENGINE_COLORS.get(e, "#6B7280") for e in engines]

    for e in engines:
        m = metrics[e].get("metrics", {})
        ing = m.get("ingest", {})
        node_rates.append(ing.get("nodes_per_sec", 0.0))
        rel_rates.append(ing.get("rels_per_sec", 0.0))

    x = np.arange(len(engines))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    rects1 = ax.bar(x - width/2, node_rates, width, label='Nodes / sec', color=[ENGINE_COLORS.get(e, "#6B7280") for e in engines], alpha=0.75)
    rects2 = ax.bar(x + width/2, rel_rates, width, label='Relationships / sec', color=[ENGINE_COLORS.get(e, "#6B7280") for e in engines], hatch='//', alpha=0.95)

    ax.set_ylabel('Ingestion Throughput (Entities / Second)')
    ax.set_title('Ingestion Throughput on Stanford SNAP Dataset (18k Nodes, 125k Edges)\nStrict Hardware Limit: 0.5 vCPU, 256 MB RAM')
    ax.set_xticks(x)
    ax.set_xticklabels(engines)
    ax.set_yscale('log')
    ax.legend()
    ax.grid(True, linestyle='--', alpha=0.6, which='both')

    for rect in rects1:
        height = rect.get_height()
        if height > 0:
            ax.annotate(f'{int(height):,}',
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3), textcoords="offset points",
                        ha='center', va='bottom', fontsize=8, rotation=25)

    for rect in rects2:
        height = rect.get_height()
        if height > 0:
            ax.annotate(f'{int(height):,}',
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3), textcoords="offset points",
                        ha='center', va='bottom', fontsize=8, rotation=25)

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'ingest_throughput.png'))
    plt.close()

def plot_traversal_latencies(metrics: Dict[str, Any], output_dir: str):
    setup_plot_style()
    engines = [e for e in ENGINE_ORDER if e in metrics]
    if not engines:
        return

    hops = ['1-Hop', '2-Hop', '3-Hop']
    hop_keys = ['traversal_1hop', 'traversal_2hop', 'traversal_3hop']
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), sharey=True)

    for idx, (stat, stat_name) in enumerate([('p50_ms', 'Median (p50)'), ('p95_ms', 'Tail (p95)')]):
        ax = axes[idx]
        x = np.arange(len(hops))
        width = 0.8 / len(engines)

        for i, engine in enumerate(engines):
            m = metrics[engine].get("metrics", {})
            vals = [m.get(k, {}).get(stat, 0.0) for k in hop_keys]
            color = ENGINE_COLORS.get(engine, "#6B7280")
            offset = (i - len(engines)/2 + 0.5) * width
            bars = ax.bar(x + offset, vals, width, label=engine, color=color, alpha=0.85)
            
            for bar in bars:
                height = bar.get_height()
                if height > 0:
                    ax.annotate(f'{height:.2f}',
                                xy=(bar.get_x() + bar.get_width() / 2, height),
                                xytext=(0, 3), textcoords="offset points",
                                ha='center', va='bottom', fontsize=7, rotation=35)

        ax.set_title(f'Multi-Hop Traversal Latency: {stat_name}')
        ax.set_xlabel('Traversal Depth')
        ax.set_ylabel('Latency in Milliseconds (Log Scale)')
        ax.set_xticks(x)
        ax.set_xticklabels(hops)
        ax.set_yscale('log')
        ax.grid(True, linestyle='--', alpha=0.6, which='both')
        if idx == 0:
            ax.legend(loc='upper left')

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'traversal_latencies.png'))
    plt.close()

def plot_lookups_and_aggregations(metrics: Dict[str, Any], output_dir: str):
    setup_plot_style()
    engines = [e for e in ENGINE_ORDER if e in metrics]
    if not engines:
        return

    workloads = ['Point Lookup\n(p50)', 'Indexed Lookup\n(p50)', 'Count Agg\n(p50)', 'Count Agg\n(p95)', 'GroupBy Agg\n(p50)', 'GroupBy Agg\n(p95)']
    
    fig, ax = plt.subplots(figsize=(13, 6))
    x = np.arange(len(workloads))
    width = 0.8 / len(engines)

    for i, engine in enumerate(engines):
        m = metrics[engine].get("metrics", {})
        vals = [
            m.get("point_lookup", {}).get("p50_ms", 0.0),
            m.get("indexed_lookup", {}).get("p50_ms", 0.0),
            m.get("aggregation_count", {}).get("p50_ms", 0.0),
            m.get("aggregation_count", {}).get("p95_ms", 0.0),
            m.get("aggregation_groupby", {}).get("p50_ms", 0.0),
            m.get("aggregation_groupby", {}).get("p95_ms", 0.0)
        ]
        color = ENGINE_COLORS.get(engine, "#6B7280")
        offset = (i - len(engines)/2 + 0.5) * width
        bars = ax.bar(x + offset, vals, width, label=engine, color=color, alpha=0.85)

        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.annotate(f'{height:.2f}',
                            xy=(bar.get_x() + bar.get_width() / 2, height),
                            xytext=(0, 3), textcoords="offset points",
                            ha='center', va='bottom', fontsize=7, rotation=35)

    ax.set_ylabel('Latency in Milliseconds (Log Scale)')
    ax.set_title('Lookups and Aggregation Latency Distributions (p50 & p95)')
    ax.set_xticks(x)
    ax.set_xticklabels(workloads)
    ax.set_yscale('log')
    ax.legend(loc='upper right')
    ax.grid(True, linestyle='--', alpha=0.6, which='both')

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'lookups_and_aggregations.png'))
    plt.close()

def plot_concurrency_scaling(metrics: Dict[str, Any], output_dir: str):
    setup_plot_style()
    engines = [e for e in ENGINE_ORDER if e in metrics]
    if not engines:
        return

    workers = [1, 10, 40]
    fig, ax = plt.subplots(figsize=(10, 6))

    for engine in engines:
        m = metrics[engine].get("metrics", {})
        qps_vals = [
            m.get("concurrency_1", {}).get("qps", 0.0),
            m.get("concurrency_10", {}).get("qps", 0.0),
            m.get("concurrency_40", {}).get("qps", 0.0)
        ]
        color = ENGINE_COLORS.get(engine, "#6B7280")
        ax.plot(workers, qps_vals, marker='o', linewidth=2.5, markersize=8, label=engine, color=color)

        for w, qps in zip(workers, qps_vals):
            if qps > 0:
                ax.annotate(f'{qps:.1f}',
                            xy=(w, qps),
                            xytext=(0, 6), textcoords="offset points",
                            ha='center', va='bottom', fontsize=8)

    ax.set_xlabel('Concurrent Clients (80% Read / 20% Write)')
    ax.set_ylabel('Throughput (Queries / Second)')
    ax.set_title('Concurrency Scaling Under 0.5 vCPU Limit (1, 10, 40 Workers)')
    ax.set_xticks(workers)
    ax.legend(loc='upper left')
    ax.grid(True, linestyle='--', alpha=0.6)

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'concurrency_scaling_qps.png'))
    plt.close()

def plot_pre_warm_vs_warmed(metrics: Dict[str, Any], output_dir: str):
    setup_plot_style()
    engines = [e for e in ENGINE_ORDER if e in metrics]
    if not engines:
        return

    cold_vals = []
    warm_vals = []

    for engine in engines:
        m = metrics[engine].get("metrics", {})
        t1 = m.get("traversal_1hop", {})
        cold_vals.append(t1.get("cold_ms", 0.0))
        warm_vals.append(t1.get("p50_ms", 0.0))

    x = np.arange(len(engines))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    rects1 = ax.bar(x - width/2, cold_vals, width, label='First-Query Latency (Pre-Warm)', color=[ENGINE_COLORS.get(e, "#6B7280") for e in engines], alpha=0.6, hatch='//')
    rects2 = ax.bar(x + width/2, warm_vals, width, label='Warmed-Cache Median (p50)', color=[ENGINE_COLORS.get(e, "#6B7280") for e in engines], alpha=0.95)

    ax.set_ylabel('Latency in Milliseconds (Log Scale)')
    ax.set_title('First-Query (Pre-Warm) vs. Warmed-Cache Latency (1-Hop Traversal)')
    ax.set_xticks(x)
    ax.set_xticklabels(engines)
    ax.set_yscale('log')
    ax.legend()
    ax.grid(True, linestyle='--', alpha=0.6, which='both')

    for rect in rects1:
        height = rect.get_height()
        if height > 0:
            ax.annotate(f'{height:.1f}ms',
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3), textcoords="offset points",
                        ha='center', va='bottom', fontsize=8, rotation=25)

    for rect in rects2:
        height = rect.get_height()
        if height > 0:
            ax.annotate(f'{height:.2f}ms',
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3), textcoords="offset points",
                        ha='center', va='bottom', fontsize=8, rotation=25)

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'pre_warm_vs_warmed_traversal.png'))
    plt.savefig(os.path.join(output_dir, 'cold_vs_warm_traversal.png'))
    plt.close()

def generate_all_charts(metrics_json_path: str, output_dir: str):
    if not os.path.exists(metrics_json_path):
        print(f"Metrics file not found: {metrics_json_path}")
        return

    with open(metrics_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    engines_data = data.get("engines", {})
    os.makedirs(output_dir, exist_ok=True)

    print(f"Generating charts from {metrics_json_path} for {len(engines_data)} engines...")
    plot_ingest_throughput(engines_data, output_dir)
    plot_traversal_latencies(engines_data, output_dir)
    plot_lookups_and_aggregations(engines_data, output_dir)
    plot_concurrency_scaling(engines_data, output_dir)
    plot_pre_warm_vs_warmed(engines_data, output_dir)
    print(f"Successfully generated all 5 high-resolution charts in {output_dir}")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(base_dir, "results", "metrics.json")
    charts_dir = os.path.join(base_dir, "results", "charts")
    generate_all_charts(json_path, charts_dir)

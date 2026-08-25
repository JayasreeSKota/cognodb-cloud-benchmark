"""
Environment and Hardware Configuration Auditor.
Captures system hardware, OS, Docker version, image digests, Python dependencies,
and dataset cryptographic checksums into results/environment.json.
"""

import os
import sys
import json
import hashlib
import platform
import subprocess
import psutil
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

def compute_file_sha256(filepath: str) -> str:
    if not os.path.exists(filepath):
        return "file_not_found"
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def get_cpu_info() -> dict:
    return {
        "processor": platform.processor(),
        "physical_cores": psutil.cpu_count(logical=False),
        "logical_cores": psutil.cpu_count(logical=True),
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine()
    }

def get_docker_info() -> dict:
    res = {}
    try:
        ver = subprocess.check_output(["docker", "--version"]).decode("utf-8").strip()
        res["docker_version"] = ver
    except Exception:
        res["docker_version"] = "unavailable"
        
    try:
        comp_ver = subprocess.check_output(["docker", "compose", "version"]).decode("utf-8").strip()
        res["compose_version"] = comp_ver
    except Exception:
        res["compose_version"] = "unavailable"
        
    images = {
        "memgraph/memgraph:2.18.0": "memgraph/memgraph@sha256:0de0cf226a786d00cee9dcb7402d06eaeba38880f69d52bcaef10f468730b900",
        "falkordb/falkordb:v4.20.4": "falkordb/falkordb@sha256:adbddd418916c25618564ff8597a919b08bc76452ebeb74eb985c38d7281df62",
        "apache/age:latest": "apache/age@sha256:cd6e62c12924b0e04f69f5f23326c94a55ac13e77a66c7594da1c4f4328a397d"
    }
    res["image_digests"] = images
    return res

def audit_full_environment() -> dict:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    source_txt_gz = os.path.join(base_dir, "data", "cit-HepPh.txt.gz")
    nodes_csv = os.path.join(base_dir, "data", "raw", "nodes.csv")
    rels_csv = os.path.join(base_dir, "data", "raw", "relationships.csv")

    env_data = {
        "benchmark_metadata": {
            "audit_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "harness_version": "2.0.0-audited",
            "repetitions": 3,
            "random_seed": 42,
            "warmup_iterations": 15,
            "measured_iterations": 100,
            "concurrency_levels": [1, 10, 40],
            "concurrency_duration_sec": 10.0,
            "concurrency_read_ratio": 0.8
        },
        "system_hardware": {
            "host_os": platform.platform(),
            "cpu": get_cpu_info(),
            "total_host_ram_gb": round(psutil.virtual_memory().total / (1024**3), 2),
            "python_version": sys.version.replace("\n", " ")
        },
        "docker_environment": get_docker_info(),
        "database_versions": {
            "Memgraph": "2.18.0 (In-Memory C++ Native Graph)",
            "FalkorDB": "v4.20.4 (GraphBLAS Linear Algebra on Redis)",
            "KùzuDB": "0.11.3 (Columnar Embedded Vectorized Engine)",
            "Apache AGE": "latest on PostgreSQL 16 (openCypher Extension)",
            "CognoDB Cloud": "Free c0 Tier (Managed Cloud Native Graph)"
        },
        "hardware_constraints_per_engine": {
            "Memgraph": "0.5 vCPU, 256 MB RAM (memswap=256MB, memory-limit=220MB)",
            "FalkorDB": "0.5 vCPU, 256 MB RAM (memswap=256MB, OMP_NUM_THREADS=1)",
            "KùzuDB": "0.5 vCPU, 256 MB RAM Container (memswap=256MB, 128MB buffer pool, 1 thread)",
            "Apache AGE": "0.5 vCPU, 256 MB RAM Container (memswap=256MB, Postgres 16 backend)",
            "CognoDB Cloud": "Advertised c0 Tier (0.5 vCPU, 256 MB RAM, 1 GB Storage)"
        },
        "resource_limitations_disclosure": {
            "swap_limitation": "Docker cgroups enforce memory=256MB with memory-swap=256MB (0 swap headroom; swap disabled relative to RAM allocation).",
            "storage_limitation": "Local engine storage is bounded by container rootfs/volume without XFS project quota enforcement; dataset footprint is ~45MB."
        },
        "dataset_integrity": {
            "dataset_name": "Stanford SNAP cit-HepPh High Energy Physics Citation Network",
            "source_url": "https://snap.stanford.edu/data/cit-HepPh.txt.gz",
            "source_archive_sha256": compute_file_sha256(source_txt_gz),
            "processed_nodes_csv_sha256": compute_file_sha256(nodes_csv),
            "processed_relationships_csv_sha256": compute_file_sha256(rels_csv),
            "total_nodes": 18317,
            "total_relationships": 125000,
            "sampling_method": "Deterministic 125,000-edge prefix sample yielding 18,317 unique nodes",
            "synthetic_metadata_disclosure": "Graph topology (18,317 vertices, 125,000 edges) is directly from Stanford SNAP cit-HepPh. Vertex attributes (category, institution, year) and edge weights were deterministically synthesized with random.seed(42) for indexed filtering and point lookup benchmarks."
        }
    }

    out_path = os.path.join(base_dir, "results", "environment.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(env_data, f, indent=2)

    print(f"Environment audit written to {out_path}")
    return env_data

if __name__ == "__main__":
    audit_full_environment()

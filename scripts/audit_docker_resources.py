"""
Audit and verify actual Docker container resource constraints (CPU quota, RAM, swap, storage).
Saves audit report to results/docker_resource_audit.json.
"""

import json
import subprocess
import os

CONTAINERS = [
    "benchmark-kuzu",
    "benchmark-memgraph",
    "benchmark-falkordb",
    "benchmark-age"
]

def audit_containers() -> dict:
    results = {}
    for name in CONTAINERS:
        try:
            out = subprocess.check_output(["docker", "inspect", name], stderr=subprocess.PIPE)
            data = json.loads(out.decode("utf-8"))[0]
            host_cfg = data.get("HostConfig", {})
            state = data.get("State", {})
            image = data.get("Config", {}).get("Image", "")
            
            nano_cpus = host_cfg.get("NanoCpus", 0)
            cpu_quota = host_cfg.get("CpuQuota", 0)
            cpu_period = host_cfg.get("CpuPeriod", 0)
            memory_bytes = host_cfg.get("Memory", 0)
            memory_swap_bytes = host_cfg.get("MemorySwap", 0)
            
            # Calculate effective vCPU and RAM
            effective_vcpu = nano_cpus / 1e9 if nano_cpus > 0 else (cpu_quota / cpu_period if cpu_period > 0 else "unconstrained")
            memory_mb = memory_bytes / (1024 * 1024) if memory_bytes > 0 else "unconstrained"
            swap_mb = (memory_swap_bytes - memory_bytes) / (1024 * 1024) if memory_swap_bytes > memory_bytes else 0
            
            results[name] = {
                "container_id": data.get("Id", "")[:12],
                "image": image,
                "status": state.get("Status", "unknown"),
                "nano_cpus": nano_cpus,
                "effective_vcpu": effective_vcpu,
                "memory_bytes": memory_bytes,
                "memory_mb": memory_mb,
                "memory_swap_bytes": memory_swap_bytes,
                "effective_swap_mb": swap_mb,
                "storage_quota_note": "OverlayFS on WSL2/Linux host without XFS project quota; actual disk store measured and reported per database."
            }
        except Exception as e:
            results[name] = {"error": str(e)}
            
    os.makedirs("results", exist_ok=True)
    out_path = os.path.join("results", "docker_resource_audit.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
        
    print(f"Docker resource audit written to {out_path}")
    for name, r in results.items():
        if "error" in r:
            print(f"  [ERROR] {name}: {r['error']}")
        else:
            print(f"  [AUDIT] {name}: vCPU={r['effective_vcpu']} | RAM={r['memory_mb']}MB | Swap={r['effective_swap_mb']}MB | Status={r['status']}")
    return results

if __name__ == "__main__":
    audit_containers()

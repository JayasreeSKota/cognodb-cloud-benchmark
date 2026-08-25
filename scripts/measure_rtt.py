"""
Network Round-Trip Time (RTT) Measurement Tool.
Measures TCP and Bolt handshake latency from the benchmark client to CognoDB Cloud.
Stores results in results/rtt_measurements.json.
"""

import os
import sys
import time
import socket
import json
from urllib.parse import urlparse
from dotenv import load_dotenv
import numpy as np

load_dotenv()

def measure_rtt(host: str, port: int = 7687, num_samples: int = 30) -> dict:
    latencies = []
    for _ in range(num_samples):
        t0 = time.perf_counter()
        try:
            s = socket.create_connection((host, port), timeout=5.0)
            s.close()
            rtt_ms = (time.perf_counter() - t0) * 1000.0
            latencies.append(rtt_ms)
        except Exception as e:
            print(f"RTT ping error: {e}")
            break
        time.sleep(0.05)

    if not latencies:
        return {"error": f"Failed to connect to {host}:{port}"}

    arr = np.array(latencies, dtype=np.float64)
    res = {
        "target_host": host,
        "target_port": port,
        "samples_count": len(latencies),
        "min_rtt_ms": round(float(np.min(arr)), 2),
        "median_rtt_ms": round(float(np.percentile(arr, 50)), 2),
        "mean_rtt_ms": round(float(np.mean(arr)), 2),
        "p95_rtt_ms": round(float(np.percentile(arr, 95)), 2),
        "max_rtt_ms": round(float(np.max(arr)), 2),
        "std_rtt_ms": round(float(np.std(arr)), 2)
    }
    return res

def run_rtt_audit():
    uri = os.getenv("COGNODB_URI", "")
    if not uri:
        print("[RTT AUDIT] COGNODB_URI not set. Measuring localhost baseline only.")
        host = "127.0.0.1"
        port = 7687
    else:
        parsed = urlparse(uri)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 7687

    print(f"Measuring Network RTT to {host}:{port} (30 samples)...")
    res = measure_rtt(host, port)
    
    os.makedirs("results", exist_ok=True)
    out_path = os.path.join("results", "rtt_measurements.json")
    res_to_save = dict(res)
    if "cognodb.com" in res_to_save.get("target_host", ""):
        res_to_save["target_host"] = "db-<instance-id>.databases.cognodb.com"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(res_to_save, f, indent=2)

    print(f"RTT measurements written to {out_path}:")
    print(f"  Min RTT:    {res.get('min_rtt_ms')} ms")
    print(f"  Median RTT: {res.get('median_rtt_ms')} ms")
    print(f"  p95 RTT:    {res.get('p95_rtt_ms')} ms")
    print(f"  Mean RTT:   {res.get('mean_rtt_ms')} ms")
    return res

if __name__ == "__main__":
    run_rtt_audit()

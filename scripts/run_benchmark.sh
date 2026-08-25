#!/usr/bin/env bash
# ==============================================================================
# One-Command Reproduction Script for Graph Database Benchmark Suite
# Evaluates CognoDB Cloud, Memgraph, FalkorDB, KùzuDB, and Apache AGE under
# strict resource parity (0.5 vCPU, 256 MB RAM, 1 GB Storage).
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

echo "======================================================================"
echo " GRAPH DATABASE BENCHMARK: ONE-COMMAND REPRODUCTION PATH"
echo " Target Hardware Constraint: 0.5 vCPU, 256 MB RAM, 1 GB Storage"
echo " Dataset: Stanford SNAP cit-HepPh (18,317 nodes, 125,000 edges)"
echo "======================================================================"

# 1. Environment & Python Verification
if [ -d "venv" ]; then
    PYTHON_EXEC="./venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON_EXEC="python3"
else
    PYTHON_EXEC="python"
fi

echo "[1/8] Verifying Python dependencies..."
${PYTHON_EXEC} -c "import psycopg2, neo4j, falkordb, kuzu, redis, pandas, numpy, matplotlib, seaborn, requests; print('  -> All dependencies verified.')"

# 2. Check and prepare dataset
echo "[2/8] Preparing and verifying immutable SNAP dataset..."
${PYTHON_EXEC} -c "from data.download_dataset import process_public_graph; process_public_graph()"

# 3. Start and verify containers
echo "[3/8] Starting Docker containers with strict resource parity..."
cd "${ROOT_DIR}/docker"
docker compose up -d
cd "${ROOT_DIR}"

echo "Waiting 12s for container DBMS initialization..."
sleep 12

# 4. Audit Docker Resource Limits
echo "[4/8] Auditing actual container resource allocations..."
${PYTHON_EXEC} scripts/audit_docker_resources.py

# 5. Connection Test
echo "[5/8] Verifying connectivity to all active database instances..."
${PYTHON_EXEC} test_connection.py

# 6. Run Complete Benchmark Suite (3 Repetitions)
echo "[6/8] Executing benchmark suite (3 repetitions with database resets)..."
${PYTHON_EXEC} run_all.py --repetitions 3 "$@"

# 7. Verify Query Semantic Parity
echo "[7/8] Running query semantic parity tests..."
${PYTHON_EXEC} scripts/verify_query_equivalence.py

# 8. Strict Deliverable Validation
echo "[8/8] Running strict deliverable validation..."
${PYTHON_EXEC} scripts/validate_results.py

echo "======================================================================"
echo "[SUCCESS] Benchmark run, validation, and artifact generation complete!"
echo "Generated Artifacts:"
echo "  - Headline Metrics:  results/metrics.json"
echo "  - Summary Table:     results/summary.csv"
echo "  - Variance Report:   results/variance.csv"
echo "  - Environment Audit: results/environment.json"
echo "  - Docker Audit:      results/docker_resource_audit.json"
echo "  - RTT Measurements:  results/rtt_measurements.json"
echo "  - Visualizations:    results/charts/*.png"
echo "======================================================================"

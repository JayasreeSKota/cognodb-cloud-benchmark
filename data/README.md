# Dataset Provenance & Specifications

This directory contains the public graph dataset used across all benchmark engines.

## 1. Dataset Source
- **Origin**: Stanford Large Network Dataset Collection (**SNAP**)
- **Dataset**: High Energy Physics Citation Network (`cit-HepPh`)
- **Source URL**: [https://snap.stanford.edu/data/cit-HepPh.txt.gz](https://snap.stanford.edu/data/cit-HepPh.txt.gz)
- **Source File SHA-256**: `917e77b3344aed33fd2d849443c9512b7c528b9dc87251d4245fb3777bbe4128`

## 2. Processed Subgraph Statistics
- **Node Count**: **18,317** unique papers / entities
- **Relationship Count**: **125,000** directed citation relationships (`CITES`)
- **Node Schema**:
  - `id`: Unique integer identifier (`0 .. 18,316`)
  - `raw_snap_id`: Original SNAP node ID
  - `name`: String identifier (`Paper_<id>`)
  - `year`: Publication year (`1992 - 2003`)
  - `category`: Research subfield (e.g., `Astrophysics`, `Quantum Gravity`, `High Energy Physics`)
  - `institution`: Affiliated institution (e.g., `CERN`, `Stanford`, `MIT`, `Max Planck`)
- **Relationship Schema**:
  - `src_id`: Source node integer ID
  - `dst_id`: Target node integer ID
  - `type`: `CITES`
  - `weight`: Integer context weight (`1 - 10`)

## 3. Immutability & Checksums
All engines load the exact same CSV files generated in `data/raw/`:
- `data/raw/nodes.csv`
- `data/raw/relationships.csv`

Verification checksums are tracked in [`checksums.txt`](checksums.txt).

## 4. Synthetic Metadata Disclosure
The graph topology (18,317 papers, 125,000 citations) is extracted directly from the Stanford SNAP `cit-HepPh` dataset. Vertex attributes (`category`, `institution`, `year`) and edge `weight` were deterministically synthesized with a fixed seed (`random.seed(42)` in `data/download_dataset.py`) to evaluate indexed filtering and point lookup operations.

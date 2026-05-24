#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$ROOT/src"

PDF_DIR="$ROOT/医疗赛题/相关样例"
XLSX="$PDF_DIR/医疗文档问答示例 - MinerU.xlsx"
OUT="$ROOT/data/runs/sample_kb"

python3 -m minderu.cli ingest --input "$PDF_DIR" --output "$OUT"
python3 -m minderu.cli inspect --index "$OUT/index.json"
python3 -m minderu.cli eval --index "$OUT/index.json" --samples-xlsx "$XLSX" --output "$OUT/eval"

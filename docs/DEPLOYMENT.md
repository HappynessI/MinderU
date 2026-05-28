# Deployment Guide

This guide describes the minimal deployment path for the competition demo.

## Runtime Requirements

- Python 3.10 or newer.
- `pdfinfo` and `pdftotext` from Poppler when ingesting PDFs without MinerU JSON.
- No Python runtime dependency is required for the default HTTP API.

Optional quality upgrades:

- MinerU JSON outputs for better reading order, tables, images, and OCR.
- `sentence-transformers` for dense retrieval inside the hybrid retriever.
- A reverse proxy such as Nginx if the benchmark platform requires TLS or external routing.

## Build Index

```bash
cd /Data/wyh/MinderU
export PYTHONPATH="$PWD/src"

python3 -m minderu.cli ingest \
  --input "医疗赛题/相关样例" \
  --output data/runs/sample_kb
```

With existing MinerU output:

```bash
python3 -m minderu.cli ingest \
  --input /path/to/pdfs \
  --mineru-dir /path/to/mineru_outputs \
  --output data/runs/competition_kb
```

The `--mineru-dir` layout can be either `<pdf_stem>/auto/<pdf_stem>_content_list.json`, `<pdf_stem>/<pdf_stem>_content_list.json`, `<pdf_stem>_content_list.json`, or `<pdf_stem>.json`.

## Start API

```bash
python3 -m minderu.cli api \
  --index data/runs/sample_kb/index.json \
  --host 0.0.0.0 \
  --port 8000
```

Hybrid retrieval without dense dependencies:

```bash
python3 -m minderu.cli api \
  --index data/runs/sample_kb/index.json \
  --host 0.0.0.0 \
  --port 8000 \
  --retriever hybrid
```

Hybrid retrieval with dense embeddings:

```bash
python3 -m minderu.cli api \
  --index data/runs/sample_kb/index.json \
  --host 0.0.0.0 \
  --port 8000 \
  --retriever hybrid \
  --embedding-model paraphrase-multilingual-MiniLM-L12-v2
```

Optional cross-encoder reranking:

```bash
python3 -m minderu.cli api \
  --index data/runs/sample_kb/index.json \
  --host 0.0.0.0 \
  --port 8000 \
  --retriever hybrid \
  --embedding-model paraphrase-multilingual-MiniLM-L12-v2 \
  --reranker cross-encoder \
  --reranker-model cross-encoder/ms-marco-MiniLM-L-6-v2
```

Smoke test:

```bash
curl -s http://127.0.0.1:8000/health
curl -s -X POST http://127.0.0.1:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"question":"请根据输入的文献内容，提取摘要中的结果部分内容","source_hint":"seyfarth2008.pdf"}'
```

Retrieval-only evaluation:

```bash
python3 -m minderu.cli eval-retrieval \
  --index data/runs/sample_kb/index.json \
  --samples-xlsx "医疗赛题/相关样例/医疗文档问答示例 - MinerU.xlsx" \
  --output data/runs/sample_kb/retrieval_eval
```

## Operational Notes

- `data/runs/` is a local artifact directory and is intentionally ignored by git.
- Use `source_hint` only when the product or benchmark request already identifies the target document.
- For pure blind retrieval, omit `source_hint`.
- The default server is suitable for demo and benchmark calls with modest concurrency. For production traffic, wrap the same query function in FastAPI or another ASGI server.

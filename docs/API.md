# MinderU API

MinderU exposes a small HTTP API for the medical literature RAG demo. The API is intentionally narrow: it answers questions against a prebuilt document index and returns evidence citations for every answer.

## Start Server

```bash
cd /Data/wyh/MinderU
export PYTHONPATH="$PWD/src"
python3 -m minderu.cli api --index data/runs/sample_kb/index.json --host 0.0.0.0 --port 8000
```

For local testing, use `--host 127.0.0.1`. For platform evaluation, run behind the host, port, reverse proxy, and authentication requirements provided by the benchmark platform.

## Health Check

```http
GET /health
```

Response:

```json
{"ok": true}
```

## List Documents

```http
GET /documents
```

Response:

```json
{
  "documents": [
    {
      "doc_id": "6995e0537fefb4c6",
      "title": "todo1992",
      "pages": 4,
      "source": "todo1992.pdf",
      "parser": "poppler"
    }
  ]
}
```

The response never exposes local absolute file paths.

## Query

```http
POST /query
Content-Type: application/json
```

Request:

```json
{
  "question": "请根据输入的文献内容，提取摘要中的结果部分内容",
  "source_hint": "seyfarth2008.pdf",
  "top_k": 6
}
```

Fields:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `question` | string | yes | User question to answer from the indexed medical literature. |
| `source_hint` | string | no | Optional document title or PDF filename. Use this when the product flow has already selected a document. |
| `top_k` | integer | no | Number of evidence chunks to retrieve. Clamped to 1-20. Default is 6. |

The server-side retriever is selected at startup:

```bash
python3 -m minderu.cli api \
  --index data/runs/sample_kb/index.json \
  --retriever hybrid \
  --embedding-model paraphrase-multilingual-MiniLM-L12-v2
```

`--retriever hybrid` supports BM25 + optional dense retrieval + reciprocal rank fusion. If `--embedding-model` is omitted, it preserves the zero-dependency BM25 behavior.

Response:

```json
{
  "answer": "- Results In 25 patients the allocated device ...",
  "citations": [
    {
      "rank": 1,
      "score": 46.945005,
      "doc_id": "b16bdf8677f4ab6a",
      "title": "seyfarth2008",
      "page_start": 1,
      "page_end": 1,
      "chunk_id": "example",
      "chunk_type": "text",
      "section_path": [],
      "snippet": "Results In 25 patients ..."
    }
  ],
  "retrieved": [],
  "source_hint": "seyfarth2008.pdf"
}
```

## Error Responses

| Status | Condition |
| --- | --- |
| 400 | Invalid JSON, missing `question`, or non-integer `top_k`. |
| 404 | Unknown path. |
| 500 | Web demo asset missing. |

## MedBench Adapter Notes

The public MedBench note only states that API submissions should expose model capability through HTTP and provide API documentation. If the official application returns a different request/response schema, add a thin adapter endpoint that maps platform fields into `question`, `source_hint`, and `top_k`, then maps MinderU citations back to the required answer format.

For the file-upload evaluation route, use:

```bash
python3 -m minderu.cli eval \
  --index data/runs/sample_kb/index.json \
  --samples-xlsx "医疗赛题/相关样例/医疗文档问答示例 - MinerU.xlsx" \
  --output data/runs/sample_kb/eval
```

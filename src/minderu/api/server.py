from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from minderu.indexing.store import load_index
from minderu.qa import answer_question
from minderu.utils import read_json

WEB_DIR = Path(__file__).resolve().parents[1] / "web"


class QueryHandler(BaseHTTPRequestHandler):
    index = None
    documents = []
    retriever = "bm25"
    reranker = "rules"
    reranker_model = None
    rerank_pool = 50
    evidence_by_id = {}
    pages_by_key = {}
    tables_by_id = {}

    def _send_bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send_bytes(status, body, "application/json; charset=utf-8")

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in {"/", "/demo"}:
            self._serve_web()
        elif path == "/health":
            self._json(200, {"ok": True, "retriever": self.retriever})
        elif path == "/documents":
            self._json(200, {"documents": self.documents})
        elif path.startswith("/evidence/"):
            self._serve_evidence(path)
        elif path.startswith("/documents/") and "/pages/" in path:
            self._serve_page(path)
        elif path.startswith("/tables/"):
            self._serve_table(path)
        else:
            self._json(404, {"error": "not found"})

    def _serve_evidence(self, path: str) -> None:
        evidence_id = path.rsplit("/", 1)[-1]
        evidence = self.evidence_by_id.get(evidence_id)
        if not evidence:
            self._json(404, {"error": "evidence not found"})
            return
        self._json(200, {"evidence": evidence})

    def _serve_page(self, path: str) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 4 or parts[0] != "documents" or parts[2] != "pages":
            self._json(404, {"error": "not found"})
            return
        try:
            page = int(parts[3])
        except ValueError:
            self._json(400, {"error": "page must be an integer"})
            return
        page_record = self.pages_by_key.get((parts[1], page))
        if not page_record:
            self._json(404, {"error": "page not found"})
            return
        self._json(200, page_record)

    def _serve_table(self, path: str) -> None:
        evidence_id = path.rsplit("/", 1)[-1]
        table = self.tables_by_id.get(evidence_id)
        if not table:
            self._json(404, {"error": "table evidence not found"})
            return
        self._json(200, {"table": table})

    def _serve_web(self) -> None:
        index_path = WEB_DIR / "index.html"
        try:
            body = index_path.read_bytes()
        except OSError:
            self._json(500, {"error": "web demo asset missing"})
            return
        self._send_bytes(200, body, "text/html; charset=utf-8")

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/query":
            self._json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._json(400, {"error": "invalid Content-Length"})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "invalid JSON body"})
            return
        if not isinstance(payload, dict):
            self._json(400, {"error": "JSON body must be an object"})
            return
        question = str(payload.get("question", "")).strip()
        if not question:
            self._json(400, {"error": "question is required"})
            return
        try:
            top_k = int(payload.get("top_k", 6))
        except (TypeError, ValueError):
            self._json(400, {"error": "top_k must be an integer"})
            return
        top_k = max(1, min(top_k, 20))
        self._json(
            200,
            answer_question(
                self.index,
                question,
                top_k=top_k,
                source_hint=payload.get("source_hint"),
                reranker=self.reranker,
                reranker_model=self.reranker_model,
                rerank_pool=self.rerank_pool,
            ),
        )


def configure_handler(
    index_path: str | Path,
    retriever: str = "bm25",
    embedding_model: str | None = None,
    reranker: str = "rules",
    reranker_model: str | None = None,
    rerank_pool: int = 50,
) -> None:
    docs, _, index = load_index(index_path, retriever=retriever, embedding_model=embedding_model)
    QueryHandler.index = index
    QueryHandler.retriever = retriever
    QueryHandler.reranker = reranker
    QueryHandler.reranker_model = reranker_model
    QueryHandler.rerank_pool = rerank_pool
    QueryHandler.documents = [
        {
            "doc_id": doc.doc_id,
            "title": doc.title,
            "pages": doc.pages,
            "source": Path(doc.path).name,
            "parser": doc.metadata.get("parser"),
        }
        for doc in docs
    ]
    _configure_graph_maps(index_path)


def _configure_graph_maps(index_path: str | Path) -> None:
    payload = read_json(index_path)
    evidence_by_id = {}
    pages_by_key = {}
    tables_by_id = {}
    for graph in payload.get("graphs", []):
        doc_id = graph.get("doc_id")
        blocks_by_id = {block.get("block_id"): block for block in graph.get("blocks", [])}
        evidence_by_chunk = {ev.get("chunk_id"): ev for ev in graph.get("evidence_spans", [])}
        for evidence in graph.get("evidence_spans", []):
            evidence_id = evidence.get("evidence_id")
            if not evidence_id:
                continue
            evidence_by_id[evidence_id] = evidence
            if str(evidence.get("evidence_type", "")).startswith("table"):
                assets = _table_assets(evidence)
                if assets:
                    tables_by_id[evidence_id] = {"evidence_id": evidence_id, **assets, "metadata": evidence.get("metadata", {})}
        for page in graph.get("pages", []):
            page_num = page.get("page")
            if doc_id is None or page_num is None:
                continue
            pages_by_key[(doc_id, page_num)] = {
                "doc_id": doc_id,
                "page": page_num,
                "blocks": [blocks_by_id[block_id] for block_id in page.get("element_ids", []) if block_id in blocks_by_id],
                "evidence": [
                    evidence_by_chunk[chunk_id]
                    for chunk_id in page.get("chunk_ids", [])
                    if chunk_id in evidence_by_chunk
                ],
            }
    QueryHandler.evidence_by_id = evidence_by_id
    QueryHandler.pages_by_key = pages_by_key
    QueryHandler.tables_by_id = tables_by_id


def _table_assets(evidence: dict) -> dict:
    metadata = evidence.get("metadata", {})
    assets = {}
    for key in ("table_html", "markdown"):
        if key in metadata:
            assets[key] = metadata[key]
    return assets


def serve(
    index_path: str | Path,
    host: str = "127.0.0.1",
    port: int = 8000,
    retriever: str = "bm25",
    embedding_model: str | None = None,
    reranker: str = "rules",
    reranker_model: str | None = None,
    rerank_pool: int = 50,
) -> None:
    configure_handler(
        index_path,
        retriever=retriever,
        embedding_model=embedding_model,
        reranker=reranker,
        reranker_model=reranker_model,
        rerank_pool=rerank_pool,
    )
    server = ThreadingHTTPServer((host, port), QueryHandler)
    print(f"MinderU demo listening on http://{host}:{port}")
    print(f"retriever={retriever}{' embedding_model=' + embedding_model if embedding_model else ''}")
    print("POST /query with JSON: {\"question\": \"...\", \"top_k\": 6}")
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--retriever", choices=("bm25", "hybrid"), default="bm25")
    parser.add_argument("--embedding-model", default=None)
    parser.add_argument("--reranker", choices=("none", "rules", "cross-encoder"), default="rules")
    parser.add_argument("--reranker-model", default=None)
    parser.add_argument("--rerank-pool", type=int, default=50)
    args = parser.parse_args()
    serve(
        args.index,
        args.host,
        args.port,
        retriever=args.retriever,
        embedding_model=args.embedding_model,
        reranker=args.reranker,
        reranker_model=args.reranker_model,
        rerank_pool=args.rerank_pool,
    )


if __name__ == "__main__":
    main()

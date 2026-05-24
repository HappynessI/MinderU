from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from minderu.indexing.store import load_index
from minderu.qa import answer_question

WEB_DIR = Path(__file__).resolve().parents[1] / "web"


class QueryHandler(BaseHTTPRequestHandler):
    index = None
    documents = []

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
            self._json(200, {"ok": True})
        elif path == "/documents":
            self._json(200, {"documents": self.documents})
        else:
            self._json(404, {"error": "not found"})

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
            ),
        )


def configure_handler(index_path: str | Path) -> None:
    docs, _, index = load_index(index_path)
    QueryHandler.index = index
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


def serve(index_path: str | Path, host: str = "127.0.0.1", port: int = 8000) -> None:
    configure_handler(index_path)
    server = ThreadingHTTPServer((host, port), QueryHandler)
    print(f"MinderU demo listening on http://{host}:{port}")
    print("POST /query with JSON: {\"question\": \"...\", \"top_k\": 6}")
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    serve(args.index, args.host, args.port)


if __name__ == "__main__":
    main()

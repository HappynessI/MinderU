from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from minderu.indexing.store import load_index
from minderu.qa import answer_question


class QueryHandler(BaseHTTPRequestHandler):
    index = None

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if urlparse(self.path).path == "/health":
            self._json(200, {"ok": True})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/query":
            self._json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        question = str(payload.get("question", "")).strip()
        if not question:
            self._json(400, {"error": "question is required"})
            return
        self._json(
            200,
            answer_question(
                self.index,
                question,
                top_k=int(payload.get("top_k", 6)),
                source_hint=payload.get("source_hint"),
            ),
        )


def serve(index_path: str | Path, host: str = "127.0.0.1", port: int = 8000) -> None:
    _, _, index = load_index(index_path)
    QueryHandler.index = index
    server = ThreadingHTTPServer((host, port), QueryHandler)
    print(f"MinderU API listening on http://{host}:{port}")
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

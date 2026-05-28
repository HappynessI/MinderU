from __future__ import annotations

import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from minderu.api.server import QueryHandler, configure_handler
from minderu.indexing.store import build_index
from minderu.schema import Chunk, DocumentRecord, Element


class SilentQueryHandler(QueryHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


class ApiServerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        docs = [
            DocumentRecord(
                doc_id="doc-1",
                title="demo-paper",
                path="/private/storage/demo-paper.pdf",
                pages=2,
                metadata={"parser": "test"},
                elements=[
                    Element(
                        element_id="e1",
                        doc_id="doc-1",
                        type="page_text",
                        text="Results showed lower mortality and improved cardiac index.",
                        page_start=1,
                        page_end=1,
                    ),
                    Element(
                        element_id="e2",
                        doc_id="doc-1",
                        type="table",
                        text="Table 1. Baseline\nAge 60",
                        page_start=2,
                        page_end=2,
                        metadata={"table_html": "<table><tr><td>Age</td></tr></table>"},
                    ),
                ],
            )
        ]
        chunks = [
            Chunk(
                chunk_id="c1",
                doc_id="doc-1",
                title="demo-paper",
                text="Document: demo-paper\n\nResults showed lower mortality and improved cardiac index.",
                chunk_type="text",
                page_start=1,
                page_end=1,
                element_ids=["e1"],
            ),
            Chunk(
                chunk_id="t1",
                doc_id="doc-1",
                title="demo-paper",
                text="Document: demo-paper\n\nTable 1. Baseline\nAge 60",
                chunk_type="table",
                page_start=2,
                page_end=2,
                element_ids=["e2"],
                metadata={"evidence_type": "table", "table_html": "<table><tr><td>Age</td></tr></table>"},
            ),
        ]
        configure_handler(build_index(docs, chunks, root))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _call_handler(self, method: str, path: str, payload: dict | None = None) -> tuple[int, str, bytes]:
        handler = SilentQueryHandler.__new__(SilentQueryHandler)
        body = b"" if payload is None else json.dumps(payload).encode("utf-8")
        handler.path = path
        handler.command = method
        handler.requestline = f"{method} {path} HTTP/1.1"
        handler.request_version = "HTTP/1.1"
        handler.client_address = ("127.0.0.1", 0)
        handler.server = None
        handler.rfile = BytesIO(body)
        handler.wfile = BytesIO()
        handler.headers = {"Content-Length": str(len(body))}
        if method == "GET":
            handler.do_GET()
        elif method == "POST":
            handler.do_POST()
        else:
            raise ValueError(method)
        raw = handler.wfile.getvalue()
        head, response_body = raw.split(b"\r\n\r\n", 1)
        status = int(head.split(b" ", 2)[1])
        content_type = next(
            line.split(b":", 1)[1].strip().decode("utf-8")
            for line in head.split(b"\r\n")
            if line.lower().startswith(b"content-type:")
        )
        return status, content_type, response_body

    def _get_json(self, path: str) -> dict:
        status, _, body = self._call_handler("GET", path)
        self.assertEqual(status, 200)
        return json.loads(body.decode("utf-8"))

    def test_serves_web_demo(self) -> None:
        status, content_type, body = self._call_handler("GET", "/")

        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("医疗文献 RAG Demo", body.decode("utf-8"))

    def test_documents_are_listed_without_private_paths(self) -> None:
        payload = self._get_json("/documents")

        self.assertEqual(payload["documents"][0]["title"], "demo-paper")
        self.assertEqual(payload["documents"][0]["source"], "demo-paper.pdf")
        self.assertNotIn("path", payload["documents"][0])
        self.assertNotIn("/private/storage", json.dumps(payload, ensure_ascii=False))

    def test_query_endpoint_returns_answer_and_citations(self) -> None:
        status, _, body = self._call_handler(
            "POST",
            "/query",
            {"question": "Results mortality", "top_k": 1},
        )
        payload = json.loads(body.decode("utf-8"))

        self.assertEqual(status, 200)
        self.assertIn("mortality", payload["answer"])
        self.assertEqual(len(payload["citations"]), 1)
        self.assertIn("evidence_id", payload["citations"][0])
        self.assertIn("evidence_packages", payload)

    def test_evidence_endpoint_returns_graph_evidence(self) -> None:
        payload = self._get_json("/evidence/c1")

        self.assertEqual(payload["evidence"]["chunk_id"], "c1")
        self.assertEqual(payload["evidence"]["doc_id"], "doc-1")

    def test_page_endpoint_returns_blocks_and_evidence(self) -> None:
        payload = self._get_json("/documents/doc-1/pages/2")

        self.assertEqual(payload["page"], 2)
        self.assertEqual(payload["blocks"][0]["block_id"], "e2")
        self.assertEqual(payload["evidence"][0]["chunk_id"], "t1")

    def test_table_endpoint_returns_table_asset(self) -> None:
        payload = self._get_json("/tables/t1")

        self.assertIn("<table>", payload["table"]["table_html"])


if __name__ == "__main__":
    unittest.main()

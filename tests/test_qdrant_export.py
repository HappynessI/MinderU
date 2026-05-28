import json
import tempfile
import unittest
from pathlib import Path

from minderu.indexing.qdrant_export import export_qdrant_points
from minderu.schema import Chunk


class QdrantExportTest(unittest.TestCase):
    def test_exports_payload_only_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "points.jsonl"
            chunks = [
                Chunk(
                    "c1",
                    "d1",
                    "demo",
                    "Document: demo\n\nResults improved.",
                    "text",
                    1,
                    1,
                    metadata={"evidence_type": "text"},
                )
            ]

            export_qdrant_points(chunks, out, collection="test")

            row = json.loads(out.read_text(encoding="utf-8").strip())
            self.assertEqual(row["collection"], "test")
            self.assertEqual(row["id"], "c1")
            self.assertNotIn("vector", row)
            self.assertEqual(row["payload"]["doc_id"], "d1")


if __name__ == "__main__":
    unittest.main()

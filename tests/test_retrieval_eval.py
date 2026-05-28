import json
import tempfile
import unittest
from pathlib import Path

from minderu.eval.retrieval import evaluate_retrieval
from minderu.indexing.store import build_index
from minderu.schema import Chunk, DocumentRecord, Element


class RetrievalEvalTest(unittest.TestCase):
    def test_retrieval_eval_reads_jsonl_and_writes_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc = DocumentRecord(
                "d1",
                "demo-paper",
                "demo.pdf",
                1,
                elements=[Element("e1", "d1", "table", "Table 1. Age 60", 1, 1)],
            )
            chunk = Chunk(
                "c1",
                "d1",
                "demo-paper",
                "Document: demo-paper\n\nTable 1. Age 60",
                "table_text",
                1,
                1,
                element_ids=["e1"],
                metadata={"evidence_type": "table"},
            )
            index = build_index([doc], [chunk], root / "kb")
            samples = root / "samples.jsonl"
            samples.write_text(
                json.dumps(
                    {
                        "id": "q1",
                        "question": "提取Table 1的表格数据",
                        "source": "demo-paper.pdf",
                        "page": 1,
                        "evidence_type": "table",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            results = evaluate_retrieval(index, root / "eval", samples_jsonl=samples)

            self.assertEqual(results[0]["metrics"]["source_hit_at_1"], True)
            self.assertTrue(results[0]["evidence_packages"])
            self.assertTrue((root / "eval" / "retrieval_eval.md").exists())


if __name__ == "__main__":
    unittest.main()

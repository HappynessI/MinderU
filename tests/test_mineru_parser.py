import json
import tempfile
import unittest
from pathlib import Path

from minderu.parsers.mineru import load_mineru_document


class MinerUParserTest(unittest.TestCase):
    def test_page_idx_is_zero_based(self):
        payload = {
            "pdf_info": [
                {"para_blocks": [{"page_idx": 0, "type": "text", "text": "first"}]},
                {"para_blocks": [{"page_idx": 1, "type": "text", "text": "second"}]},
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "doc.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            doc = load_mineru_document(path)
        self.assertEqual([e.page_start for e in doc.elements], [1, 2])
        self.assertEqual(doc.pages, 2)

    def test_one_based_page_is_preserved(self):
        payload = [{"page": 3, "type": "text", "text": "third"}]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "doc.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            doc = load_mineru_document(path)
        self.assertEqual(doc.elements[0].page_start, 3)

    def test_table_and_image_assets_are_preserved(self):
        payload = [
            {
                "page_idx": 0,
                "type": "table",
                "table_caption": ["Table 1. Baseline"],
                "table_body": "<table><tr><td>Age</td></tr></table>",
                "bbox": [1, 2, 3, 4],
            },
            {
                "page_idx": 1,
                "type": "image",
                "image_caption": ["Figure 2. Flowchart"],
                "img_path": "images/figure2.png",
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "content_list.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            doc = load_mineru_document(path)
        self.assertEqual(doc.elements[0].type, "table")
        self.assertIn("<table>", doc.elements[0].text)
        self.assertEqual(doc.elements[0].bbox, [1, 2, 3, 4])
        self.assertEqual(doc.elements[0].metadata["evidence_type"], "table")
        self.assertIn("captions", doc.elements[0].metadata)
        self.assertEqual(doc.elements[1].type, "figure")
        self.assertIn("images/figure2.png", doc.elements[1].text)
        self.assertEqual(doc.elements[1].metadata["image_path"], "images/figure2.png")


if __name__ == "__main__":
    unittest.main()

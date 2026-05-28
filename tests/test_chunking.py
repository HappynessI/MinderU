import unittest

from minderu.chunking import chunk_document
from minderu.indexing.bm25 import BM25Index
from minderu.schema import Chunk, DocumentRecord, Element


class ChunkingTest(unittest.TestCase):
    def test_question_heading_becomes_section(self):
        doc = DocumentRecord(
            doc_id="d1",
            title="demo",
            path="demo.pdf",
            pages=1,
            elements=[
                Element(
                    element_id="e1",
                    doc_id="d1",
                    type="page_text",
                    text="问题四、卵巢子宫内膜异位囊肿有哪些声像图特征?\n1. 典型特征包括彩色多普勒血流显像等。",
                    page_start=2,
                    page_end=2,
                )
            ],
        )
        chunks = chunk_document(doc)
        self.assertTrue(chunks)
        self.assertTrue(chunks[0].section_path)
        self.assertEqual(chunks[0].page_start, 2)
        self.assertIn("问题四", chunks[0].text)

    def test_table_label_boosts_same_page_table_chunk(self):
        doc = DocumentRecord(
            doc_id="d1",
            title="demo",
            path="demo.pdf",
            pages=2,
            elements=[
                Element("caption", "d1", "table_caption", "Table 5. Outcome summary", 2, 2),
                Element("table", "d1", "table_text", "Patient Center OLT Alive Mental state", 2, 2),
                Element("other", "d1", "page_text", "Table 1 unrelated text", 1, 1),
            ],
        )
        chunks = chunk_document(doc)
        hits = BM25Index(chunks).search("提取图5中的表格数据", top_k=2)
        self.assertTrue(hits)
        self.assertEqual(hits[0]["chunk"]["page_start"], 2)

    def test_split_table_label_beats_same_number_figure_for_table_query(self):
        chunks = [
            Chunk(
                "fig",
                "zh",
                "ultrasound",
                "Document: ultrasound\n\n图 5 双侧卵巢子宫内膜异位囊肿 接吻征 二维灰阶声像图",
                "figure_caption",
                3,
                3,
            ),
            Chunk("label", "todo", "todo1992", "Document: todo1992\nSection: Table\n\nTABLE", "text", 3, 3),
            Chunk(
                "header",
                "todo",
                "todo1992",
                "Document: todo1992\nSection: Table\n\n5. Urea cycle enzyme deficiencies treated with OLT",
                "text",
                3,
                3,
            ),
            Chunk(
                "body",
                "todo",
                "todo1992",
                "Document: todo1992\nSection: Table\n\nPatient Center OLT deficiency Alive dead Mental state Reference",
                "table_text",
                3,
                3,
            ),
        ]

        hits = BM25Index(chunks).search("请根据输入的文献内容，提取图5中的表格数据", top_k=2)

        self.assertTrue(hits)
        self.assertEqual(hits[0]["chunk"]["title"], "todo1992")
        self.assertEqual(hits[0]["chunk"]["chunk_type"], "table_text")

    def test_page_text_splits_multiple_medical_sections(self):
        doc = DocumentRecord(
            doc_id="d1",
            title="trial",
            path="trial.pdf",
            pages=1,
            elements=[
                Element(
                    "e1",
                    "d1",
                    "page_text",
                    "Primary outcome\nMortality was lower.\nSecondary outcome\nLactate improved.",
                    1,
                    1,
                )
            ],
        )
        chunks = chunk_document(doc, max_chars=2000)
        texts = [chunk.text for chunk in chunks]
        self.assertTrue(any("Primary outcome" in text for text in texts))
        self.assertTrue(any("Secondary outcome" in text for text in texts))
        self.assertGreaterEqual(len(chunks), 2)


if __name__ == "__main__":
    unittest.main()

import unittest

from minderu.chunking import chunk_document
from minderu.schema import DocumentRecord, Element


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


if __name__ == "__main__":
    unittest.main()

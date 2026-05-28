import unittest

from minderu.chunking import chunk_document
from minderu.graph import build_document_graphs
from minderu.schema import DocumentRecord, Element


class DocumentGraphTest(unittest.TestCase):
    def test_graph_links_pages_blocks_and_evidence(self):
        doc = DocumentRecord(
            doc_id="d1",
            title="demo",
            path="demo.pdf",
            pages=1,
            elements=[
                Element(
                    "e1",
                    "d1",
                    "table",
                    "Table 1. Baseline\nAge 60",
                    1,
                    1,
                    bbox=[1, 2, 3, 4],
                    metadata={"table_html": "<table></table>"},
                )
            ],
        )
        chunks = chunk_document(doc)

        graph = build_document_graphs([doc], chunks)[0]

        self.assertEqual(graph.doc_id, "d1")
        self.assertEqual(graph.pages[0].element_ids, ["e1"])
        self.assertEqual(graph.blocks[0].bbox, [1, 2, 3, 4])
        self.assertEqual(graph.evidence_spans[0].bbox, [1, 2, 3, 4])
        self.assertEqual(graph.evidence_spans[0].evidence_type, "table")


if __name__ == "__main__":
    unittest.main()


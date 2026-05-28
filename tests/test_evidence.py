import unittest

from minderu.evidence import pack_evidence


class EvidencePackerTest(unittest.TestCase):
    def test_adjacent_same_page_table_evidence_is_packed(self):
        citations = [
            {
                "evidence_id": "caption",
                "doc_id": "d1",
                "title": "demo",
                "page_start": 2,
                "page_end": 2,
                "evidence_type": "table_caption",
                "snippet": "Table 1. Baseline",
                "assets": {},
            },
            {
                "evidence_id": "body",
                "doc_id": "d1",
                "title": "demo",
                "page_start": 2,
                "page_end": 2,
                "evidence_type": "table_text",
                "snippet": "Age 60",
                "assets": {"table_html": "<table></table>"},
            },
        ]

        packages = pack_evidence(citations)

        self.assertEqual(len(packages), 1)
        self.assertEqual(packages[0]["citation_ids"], ["caption", "body"])
        self.assertIn("table_html", packages[0]["assets"])


if __name__ == "__main__":
    unittest.main()

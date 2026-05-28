import unittest

from minderu.qa.grounded import evidence_only_answer, grounded_answer, validate_citations


class GroundedAnswerTest(unittest.TestCase):
    def test_grounded_answer_includes_valid_citation_markers(self):
        citations = [{"title": "demo", "page_start": 1, "snippet": "Results improved mortality."}]

        answer = grounded_answer("结果是什么", citations)

        self.assertIn("[E1]", answer)
        self.assertTrue(validate_citations(answer, 1))

    def test_evidence_only_lists_citations(self):
        citations = [{"title": "demo", "page_start": 2, "snippet": "Table values."}]

        answer = evidence_only_answer(citations)

        self.assertIn("[E1] demo p.2", answer)


if __name__ == "__main__":
    unittest.main()

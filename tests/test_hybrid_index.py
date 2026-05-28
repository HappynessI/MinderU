from __future__ import annotations

import unittest

from minderu.indexing.hybrid import HybridIndex
from minderu.schema import Chunk


class FakeEncoder:
    def encode(self, sentences, **kwargs):
        if isinstance(sentences, str):
            return self._vector(sentences)
        return [self._vector(sentence) for sentence in sentences]

    def _vector(self, text: str) -> list[float]:
        lowered = text.lower()
        if "heart" in lowered or "cardiac" in lowered:
            return [1.0, 0.0]
        if "renal" in lowered or "kidney" in lowered:
            return [0.0, 1.0]
        return [0.1, 0.1]


class HybridIndexTest(unittest.TestCase):
    def test_without_dense_model_falls_back_to_bm25(self) -> None:
        chunks = [
            Chunk("c1", "d1", "demo", "Document: demo\n\ncardiac index improved", "text", 1, 1),
            Chunk("c2", "d1", "demo", "Document: demo\n\nrenal function declined", "text", 2, 2),
        ]

        hits = HybridIndex(chunks).search("cardiac index", top_k=1)

        self.assertEqual(hits[0]["chunk"]["chunk_id"], "c1")

    def test_dense_model_participates_in_rrf(self) -> None:
        chunks = [
            Chunk("c1", "d1", "demo", "Document: demo\n\ncardiac index improved", "text", 1, 1),
            Chunk("c2", "d1", "demo", "Document: demo\n\nrenal function declined", "text", 2, 2),
        ]

        hits = HybridIndex(chunks, dense_model=FakeEncoder()).search("heart performance", top_k=1)

        self.assertEqual(hits[0]["chunk"]["chunk_id"], "c1")
        self.assertEqual(hits[0]["retriever"], "hybrid_rrf")


if __name__ == "__main__":
    unittest.main()


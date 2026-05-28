from __future__ import annotations

import unittest

from unittest.mock import patch

from minderu.indexing.hybrid import HybridIndex
from minderu.rerank import rerank_evidence
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


class FakeCrossEncoder:
    def __init__(self, model_name: str):
        self.model_name = model_name

    def predict(self, pairs):
        return [1.0 if "Age 60" in text else 0.1 for _, text in pairs]


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

    def test_evidence_reranker_prefers_expected_type(self) -> None:
        hits = [
            {"score": 10.0, "chunk": {"chunk_id": "text", "chunk_type": "text", "text": "Table 1 mentions baseline"}},
            {"score": 9.0, "chunk": {"chunk_id": "table", "chunk_type": "table_text", "text": "Age 60"}},
        ]

        reranked = rerank_evidence("提取Table 1的表格数据", hits)

        self.assertEqual(reranked[0]["chunk"]["chunk_id"], "table")

    def test_cross_encoder_reranker_can_be_loaded_optionally(self) -> None:
        hits = [
            {"score": 10.0, "chunk": {"chunk_id": "text", "chunk_type": "text", "text": "unrelated"}},
            {"score": 9.0, "chunk": {"chunk_id": "table", "chunk_type": "table_text", "text": "Age 60"}},
        ]
        with patch("minderu.rerank._load_cross_encoder", return_value=FakeCrossEncoder("fake")):
            reranked = rerank_evidence("提取Table 1的表格数据", hits, mode="cross-encoder", model_name="fake")

        self.assertEqual(reranked[0]["chunk"]["chunk_id"], "table")


if __name__ == "__main__":
    unittest.main()

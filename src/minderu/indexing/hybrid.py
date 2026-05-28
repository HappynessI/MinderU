from __future__ import annotations

import math
from dataclasses import asdict
from typing import Any, Protocol

from minderu.indexing.bm25 import BM25Index, PathSafe
from minderu.schema import Chunk


class Encoder(Protocol):
    def encode(self, sentences: str | list[str], **kwargs: Any) -> Any:
        ...


class HybridIndex:
    """Sparse+dense retrieval with RRF fusion.

    Dense retrieval is optional. Without an embedding model this class falls
    back to BM25, preserving the zero-dependency baseline.
    """

    def __init__(
        self,
        chunks: list[Chunk],
        dense_model_name: str | None = None,
        dense_model: Encoder | None = None,
        rrf_k: int = 60,
    ):
        self.chunks = chunks
        self.bm25 = BM25Index(chunks)
        self.rrf_k = rrf_k
        self.dense_model = dense_model or _load_sentence_transformer(dense_model_name)
        self.dense_vectors = self._encode_chunks() if self.dense_model else []

    def search(
        self,
        query: str,
        top_k: int = 8,
        source_hint: str | None = None,
        page_hint: int | None = None,
    ) -> list[dict[str, Any]]:
        if not self.dense_model:
            return self.bm25.search(query, top_k=top_k, source_hint=source_hint, page_hint=page_hint)

        pool = max(top_k * 6, 30)
        sparse_hits = self.bm25.search(query, top_k=pool, source_hint=source_hint, page_hint=page_hint)
        dense_hits = self._dense_search(query, top_k=pool, source_hint=source_hint, page_hint=page_hint)
        fused = self._rrf([sparse_hits, dense_hits])
        return fused[:top_k]

    def _encode_chunks(self) -> list[list[float]]:
        texts = [_semantic_text(chunk) for chunk in self.chunks]
        vectors = self.dense_model.encode(texts, convert_to_tensor=False, show_progress_bar=False)
        return [_as_float_list(vector) for vector in vectors]

    def _dense_search(
        self,
        query: str,
        top_k: int,
        source_hint: str | None,
        page_hint: int | None,
    ) -> list[dict[str, Any]]:
        query_vec = _as_float_list(self.dense_model.encode(query, convert_to_tensor=False))
        source_hint_lower = source_hint.lower() if source_hint else None
        scored: list[tuple[float, int]] = []
        for idx, chunk in enumerate(self.chunks):
            if not _chunk_allowed(chunk, source_hint_lower, page_hint):
                continue
            score = _cosine(query_vec, self.dense_vectors[idx])
            if score > 0:
                scored.append((score, idx))
        scored.sort(reverse=True)
        return [
            {
                "score": round(score, 6),
                "chunk": asdict(self.chunks[idx]),
                "retriever": "dense",
            }
            for score, idx in scored[:top_k]
        ]

    def _rrf(self, ranked_lists: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
        scores: dict[str, float] = {}
        best_hit: dict[str, dict[str, Any]] = {}
        retrievers: dict[str, set[str]] = {}
        for ranked in ranked_lists:
            for rank, hit in enumerate(ranked, start=1):
                chunk_id = hit["chunk"]["chunk_id"]
                scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (self.rrf_k + rank)
                if chunk_id not in best_hit or hit["score"] > best_hit[chunk_id]["score"]:
                    best_hit[chunk_id] = hit
                retrievers.setdefault(chunk_id, set()).add(str(hit.get("retriever", "bm25")))
        ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        fused: list[dict[str, Any]] = []
        for chunk_id, score in ordered:
            hit = dict(best_hit[chunk_id])
            hit["score"] = round(score, 6)
            hit["retriever"] = "hybrid_rrf"
            hit["retrievers"] = sorted(retrievers.get(chunk_id, set()))
            fused.append(hit)
        return fused


def _load_sentence_transformer(model_name: str | None) -> Encoder | None:
    if not model_name:
        return None
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "Hybrid dense retrieval requires sentence-transformers. "
            "Install the semantic optional dependencies or omit --embedding-model."
        ) from exc
    return SentenceTransformer(model_name)


def _semantic_text(chunk: Chunk) -> str:
    value = chunk.metadata.get("semantic_repr") if isinstance(chunk.metadata, dict) else None
    if isinstance(value, str) and value.strip():
        return value
    context = [chunk.title, chunk.chunk_type, " > ".join(chunk.section_path)]
    return "\n".join(part for part in context if part) + "\n\n" + chunk.text


def _as_float_list(vector: Any) -> list[float]:
    if hasattr(vector, "detach"):
        vector = vector.detach().cpu().tolist()
    elif hasattr(vector, "tolist"):
        vector = vector.tolist()
    if vector and isinstance(vector[0], list):
        vector = vector[0]
    return [float(x) for x in vector]


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    l_norm = math.sqrt(sum(a * a for a in left))
    r_norm = math.sqrt(sum(b * b for b in right))
    if l_norm == 0 or r_norm == 0:
        return 0.0
    return dot / (l_norm * r_norm)


def _chunk_allowed(chunk: Chunk, source_hint_lower: str | None, page_hint: int | None) -> bool:
    if source_hint_lower:
        title_path = (chunk.title + " " + str(chunk.metadata.get("path", ""))).lower()
        if source_hint_lower not in title_path and PathSafe.basename(source_hint_lower) not in title_path:
            return False
    if page_hint is not None:
        if chunk.page_start is None:
            return False
        if not (chunk.page_start <= page_hint <= (chunk.page_end or chunk.page_start)):
            if abs(chunk.page_start - page_hint) > 1:
                return False
    return True


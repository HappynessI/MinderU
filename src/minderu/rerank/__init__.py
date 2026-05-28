from __future__ import annotations

from functools import lru_cache
import re
from typing import Any


def rerank_evidence(
    question: str,
    hits: list[dict[str, Any]],
    mode: str = "rules",
    model_name: str | None = None,
) -> list[dict[str, Any]]:
    if mode == "none":
        return hits
    if mode == "cross-encoder" and model_name:
        return _cross_encoder_rerank(question, hits, model_name)
    expected = expected_evidence_type(question)
    if expected is None:
        return hits

    scored: list[tuple[float, int, dict[str, Any]]] = []
    for idx, hit in enumerate(hits):
        chunk = hit["chunk"]
        score = float(hit.get("score", 0.0))
        chunk_type = str(chunk.get("chunk_type", ""))
        evidence_type = str(chunk.get("metadata", {}).get("evidence_type", chunk_type))
        if _type_matches(expected, chunk_type, evidence_type):
            score += 5.0
        elif expected in {"table", "figure"} and chunk_type == "text":
            text = chunk.get("text", "")
            if expected == "table" and re.search(r"\btable\b|表\s*\d+", text, re.I):
                score += 2.0
            if expected == "figure" and re.search(r"\bfig(?:ure)?\b|图\s*\d+", text, re.I):
                score += 2.0
        scored.append((score, -idx, hit))
    scored.sort(reverse=True)
    reranked: list[dict[str, Any]] = []
    for score, _, hit in scored:
        updated = dict(hit)
        updated["score"] = round(score, 6)
        updated["reranker"] = "evidence_type_rules"
        reranked.append(updated)
    return reranked


def _cross_encoder_rerank(question: str, hits: list[dict[str, Any]], model_name: str) -> list[dict[str, Any]]:
    model = _load_cross_encoder(model_name)
    pairs = [(question, hit["chunk"].get("metadata", {}).get("semantic_repr") or hit["chunk"].get("text", "")) for hit in hits]
    scores = model.predict(pairs)
    scored: list[tuple[float, int, dict[str, Any]]] = []
    for idx, (score, hit) in enumerate(zip(scores, hits)):
        updated = dict(hit)
        updated["score"] = round(float(score), 6)
        updated["reranker"] = "cross_encoder"
        scored.append((float(score), -idx, updated))
    scored.sort(reverse=True)
    return [hit for _, _, hit in scored]


@lru_cache(maxsize=4)
def _load_cross_encoder(model_name: str) -> Any:
    try:
        from sentence_transformers import CrossEncoder
    except ImportError as exc:
        raise RuntimeError(
            "Cross-encoder reranking requires sentence-transformers. "
            "Install the semantic optional dependencies or use --reranker rules."
        ) from exc
    return CrossEncoder(model_name)


def expected_evidence_type(question: str) -> str | None:
    lowered = question.lower()
    if "table" in lowered or "表格" in question or re.search(r"(?<!图)表\s*[0-9一二三四五六七八九十]?", question):
        return "table"
    if "figure" in lowered or "fig" in lowered or "图" in question:
        return "figure"
    if "摘要" in question or "结果" in question or re.search(r"问题[一二三四五六七八九十\d]+", question):
        return "text"
    return None


def _type_matches(expected: str, chunk_type: str, evidence_type: str) -> bool:
    values = {chunk_type, evidence_type}
    if expected == "table":
        return any(value.startswith("table") or value == "table" for value in values)
    if expected == "figure":
        return any(value.startswith("figure") or value == "figure" for value in values)
    if expected == "text":
        return "text" in values or "page_text" in values
    return False

from __future__ import annotations

import re
from typing import Any


def rerank_evidence(question: str, hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
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

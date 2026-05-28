from __future__ import annotations

import re
from typing import Any


def evidence_only_answer(citations: list[dict[str, Any]]) -> str:
    if not citations:
        return "未检索到足够证据。"
    lines = []
    for idx, cite in enumerate(citations, start=1):
        page = cite.get("page_start") if cite.get("page_start") is not None else "?"
        lines.append(f"[E{idx}] {cite.get('title')} p.{page}: {cite.get('snippet', '')}")
    return "\n".join(lines)


def grounded_answer(question: str, citations: list[dict[str, Any]]) -> str:
    if not citations:
        return "未检索到足够证据。"
    bullets = []
    for idx, cite in enumerate(citations[:4], start=1):
        snippet = _compact(cite.get("snippet", ""))
        if snippet:
            bullets.append(f"- {snippet} [E{idx}]")
    answer = "\n".join(bullets) if bullets else evidence_only_answer(citations)
    if not validate_citations(answer, len(citations)):
        return evidence_only_answer(citations)
    return answer


def validate_citations(answer: str, evidence_count: int) -> bool:
    markers = [int(value) for value in re.findall(r"\[E(\d+)\]", answer)]
    return bool(markers) and all(1 <= marker <= evidence_count for marker in markers)


def _compact(text: str, limit: int = 500) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."

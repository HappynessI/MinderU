from __future__ import annotations

import re
from typing import Any

from minderu.indexing.bm25 import BM25Index, tokenize


def _clean_snippet(text: str, max_chars: int = 1200) -> str:
    text = re.sub(r"Document: .+\n", "", text)
    text = re.sub(r"Section: .+\n", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _sentence_candidates(text: str) -> list[str]:
    compact = re.sub(r"\s+", " ", text)
    parts = re.split(r"(?<=[。！？.!?])\s+|(?<=;)\s+", compact)
    return [p.strip() for p in parts if len(p.strip()) > 12]


def _best_sentences(question: str, text: str, limit: int = 4) -> list[str]:
    q_tokens = set(tokenize(question))
    scored: list[tuple[int, str]] = []
    for sent in _sentence_candidates(text):
        st = set(tokenize(sent))
        score = len(q_tokens & st)
        if re.search(r"results?|结果|结论|方法|目的|table|fig|图|表", sent, re.I):
            score += 2
        if score > 0:
            scored.append((score, sent))
    scored.sort(reverse=True)
    return [s for _, s in scored[:limit]]


def _targeted_extract(question: str, text: str, chunk_type: str, page_start: int | None = None) -> list[str]:
    q = question.lower()
    compact = re.sub(r"[ \t]+", " ", text)
    if "table" in q or "表格" in question or chunk_type.startswith("table"):
        if not chunk_type.startswith("table") and len(compact) > 1000:
            return []
        return [_clean_snippet(compact, max_chars=1600)]
    if "摘要" in question and "结果" in question:
        if page_start not in (None, 1):
            return []
        m = re.search(r"Results\s+(.*?)(?:\s+Conclusions\s+|\s+Conclusion\s+)", compact, re.I | re.S)
        if m:
            return [m.group(1).strip()]
    m = re.search(r"(问题[一二三四五六七八九十\d]+[、.．].{0,1200})", compact, re.S)
    if m and re.search(r"问题[一二三四五六七八九十\d]+", question):
        return [m.group(1).strip()]
    return []


def _page_hint(question: str) -> int | None:
    m = re.search(r"第\s*(\d+)\s*页", question)
    return int(m.group(1)) if m else None


def answer_question(index: BM25Index, question: str, top_k: int = 6, source_hint: str | None = None) -> dict[str, Any]:
    hits = index.search(question, top_k=top_k, source_hint=source_hint, page_hint=_page_hint(question))
    if not hits:
        return {
            "answer": "未检索到足够证据。请确认文献已经入库，或提高解析质量后重建索引。",
            "citations": [],
            "retrieved": [],
            "source_hint": source_hint,
        }

    evidence = []
    targeted_parts: list[str] = []
    fallback_parts: list[str] = []
    for rank, hit in enumerate(hits, start=1):
        chunk = hit["chunk"]
        raw_text = chunk["text"]
        text = _clean_snippet(raw_text)
        best = _best_sentences(question, text)
        if not best:
            best = [text]
        evidence.append(
            {
                "rank": rank,
                "score": hit["score"],
                "doc_id": chunk["doc_id"],
                "title": chunk["title"],
                "page_start": chunk["page_start"],
                "page_end": chunk["page_end"],
                "chunk_id": chunk["chunk_id"],
                "chunk_type": chunk["chunk_type"],
                "section_path": chunk.get("section_path", []),
                "snippet": text,
            }
        )
        targeted = _targeted_extract(question, raw_text, chunk["chunk_type"], chunk.get("page_start"))
        if targeted and len(targeted_parts) < 3:
            targeted_parts.extend(targeted[: max(1, 3 - len(targeted_parts))])
        if best and len(fallback_parts) < 3:
            fallback_parts.extend(best[: max(1, 3 - len(fallback_parts))])

    answer_source = targeted_parts if targeted_parts else fallback_parts
    answer = "\n".join(f"- {part}" for part in answer_source[:4])
    if re.search(r"图|figure|fig", question, re.I):
        answer += "\n\n注意：若原文目标是流程图/图片，本地零依赖解析只能定位页码、图注或附近文本；完整图像内容需要 MinerU OCR/VLM 输出或页面截图证据。"
    return {"answer": answer, "citations": evidence[:top_k], "retrieved": hits, "source_hint": source_hint}

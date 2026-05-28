from __future__ import annotations

import re
from typing import Any

from minderu.rerank import expected_evidence_type


def ranking_metrics(
    expected_source: str,
    question: str,
    citations: list[dict[str, Any]],
    hit_ks: tuple[int, ...] = (1, 3, 5),
    expected_page: int | None = None,
    expected_type: str | None = None,
) -> dict[str, Any]:
    titles = [cite["title"] for cite in citations]
    source_rank = source_rank_for(expected_source, titles)
    page = expected_page if expected_page is not None else page_hint(question)
    evidence_type = expected_type or expected_evidence_type(question)
    metrics: dict[str, Any] = {
        "source_rank": source_rank,
        "page_hint": page,
        "expected_evidence_type": evidence_type,
        "reciprocal_rank": 0.0 if source_rank is None else 1.0 / source_rank,
    }
    for k in hit_ks:
        metrics[f"source_hit_at_{k}"] = source_rank is not None and source_rank <= k
        metrics[f"page_hit_at_{k}"] = page_hit(page, citations[:k])
        metrics[f"evidence_type_hit_at_{k}"] = type_hit(evidence_type, citations[:k])
    return metrics


def summarize_metrics(results: list[dict[str, Any]], hit_ks: tuple[int, ...] = (1, 3, 5)) -> dict[str, float]:
    if not results:
        out = {"mrr": 0.0, "page_hint_count": 0.0}
        for k in hit_ks:
            out[f"source_hit_at_{k}"] = 0.0
            out[f"page_hit_at_{k}"] = 0.0
            out[f"evidence_type_hit_at_{k}"] = 0.0
        return out

    metrics = [row["metrics"] for row in results]
    typed = [item for item in metrics if item["expected_evidence_type"]]
    page_hinted = [item for item in metrics if item["page_hint"] is not None]
    out = {
        "mrr": sum(float(item["reciprocal_rank"]) for item in metrics) / len(metrics),
        "page_hint_count": float(len(page_hinted)),
    }
    for k in hit_ks:
        out[f"source_hit_at_{k}"] = sum(1 for item in metrics if item.get(f"source_hit_at_{k}")) / len(metrics)
        out[f"page_hit_at_{k}"] = (
            0.0 if not page_hinted else sum(1 for item in page_hinted if item.get(f"page_hit_at_{k}")) / len(page_hinted)
        )
        out[f"evidence_type_hit_at_{k}"] = (
            0.0 if not typed else sum(1 for item in typed if item.get(f"evidence_type_hit_at_{k}")) / len(typed)
        )
    return out


def source_rank_for(expected_source: str, titles: list[str]) -> int | None:
    if not expected_source:
        return None
    expected = expected_source.lower().removesuffix(".pdf")
    for idx, title in enumerate(titles, start=1):
        lowered = title.lower()
        if expected in lowered or lowered in expected:
            return idx
    return None


def page_hint(question: str) -> int | None:
    match = re.search(r"第\s*(\d+)\s*页", question)
    return int(match.group(1)) if match else None


def type_hit(expected_type: str | None, citations: list[dict[str, Any]]) -> bool | None:
    if expected_type is None:
        return None
    for cite in citations:
        chunk_type = str(cite.get("chunk_type", ""))
        evidence_type = str(cite.get("evidence_type", chunk_type))
        if expected_type == "table" and (chunk_type.startswith("table") or evidence_type.startswith("table")):
            return True
        if expected_type == "figure" and (chunk_type.startswith("figure") or evidence_type.startswith("figure")):
            return True
        if expected_type == "text" and (chunk_type == "text" or evidence_type in {"text", "page_text"}):
            return True
    return False


def page_hit(expected_page: int | None, citations: list[dict[str, Any]]) -> bool | None:
    if expected_page is None:
        return None
    for cite in citations:
        page_start = cite.get("page_start")
        page_end = cite.get("page_end") or page_start
        if page_start is not None and page_start <= expected_page <= page_end:
            return True
    return False


def parse_hit_ks(value: str) -> tuple[int, ...]:
    hit_ks = tuple(sorted({int(part.strip()) for part in value.split(",") if part.strip()}))
    if not hit_ks or any(k <= 0 for k in hit_ks):
        raise ValueError("top-k values must be positive integers")
    return hit_ks


from __future__ import annotations

from typing import Any


def pack_evidence(citations: list[dict[str, Any]], max_packages: int | None = None) -> list[dict[str, Any]]:
    packages: list[dict[str, Any]] = []
    for cite in citations:
        key = _package_key(cite)
        if packages and packages[-1]["package_key"] == key:
            _merge_citation(packages[-1], cite)
            continue
        packages.append(_new_package(key, cite))
    return packages[:max_packages] if max_packages is not None else packages


def _package_key(cite: dict[str, Any]) -> tuple[Any, ...]:
    page = cite.get("page_start")
    evidence_type = _coarse_type(str(cite.get("evidence_type") or cite.get("chunk_type") or "text"))
    return (cite.get("doc_id"), page, evidence_type)


def _coarse_type(value: str) -> str:
    if value.startswith("table"):
        return "table"
    if value.startswith("figure") or value == "image":
        return "figure"
    return "text"


def _new_package(key: tuple[Any, ...], cite: dict[str, Any]) -> dict[str, Any]:
    return {
        "package_key": key,
        "package_id": "::".join(str(part) for part in key),
        "doc_id": cite.get("doc_id"),
        "title": cite.get("title"),
        "page_start": cite.get("page_start"),
        "page_end": cite.get("page_end"),
        "evidence_type": _coarse_type(str(cite.get("evidence_type") or cite.get("chunk_type") or "text")),
        "citation_ids": [cite.get("evidence_id") or cite.get("chunk_id")],
        "citations": [cite],
        "snippets": [cite.get("snippet", "")],
        "assets": dict(cite.get("assets") or {}),
        "bbox": cite.get("bbox"),
    }


def _merge_citation(package: dict[str, Any], cite: dict[str, Any]) -> None:
    citation_id = cite.get("evidence_id") or cite.get("chunk_id")
    if citation_id not in package["citation_ids"]:
        package["citation_ids"].append(citation_id)
        package["citations"].append(cite)
    if cite.get("snippet"):
        package["snippets"].append(cite["snippet"])
    if cite.get("page_end") and (package.get("page_end") is None or cite["page_end"] > package["page_end"]):
        package["page_end"] = cite["page_end"]
    if package.get("bbox") is None and cite.get("bbox") is not None:
        package["bbox"] = cite["bbox"]
    package["assets"].update(cite.get("assets") or {})

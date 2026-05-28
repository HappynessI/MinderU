from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SourceRef:
    doc_id: str
    title: str
    path: str
    page_start: int | None = None
    page_end: int | None = None
    bbox: list[float] | None = None
    element_id: str | None = None


@dataclass
class Element:
    element_id: str
    doc_id: str
    type: str
    text: str
    page_start: int | None
    page_end: int | None
    bbox: list[float] | None = None
    section_path: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentRecord:
    doc_id: str
    title: str
    path: str
    pages: int
    elements: list[Element] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PageRecord:
    doc_id: str
    page: int
    element_ids: list[str] = field(default_factory=list)
    chunk_ids: list[str] = field(default_factory=list)


@dataclass
class BlockRecord:
    block_id: str
    doc_id: str
    type: str
    text: str
    page_start: int | None
    page_end: int | None
    bbox: list[float] | None = None
    section_path: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    title: str
    text: str
    chunk_type: str
    page_start: int | None
    page_end: int | None
    element_ids: list[str] = field(default_factory=list)
    section_path: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def source_label(self) -> str:
        if self.page_start is None:
            return self.title
        if self.page_end and self.page_end != self.page_start:
            return f"{self.title}, pp. {self.page_start}-{self.page_end}"
        return f"{self.title}, p. {self.page_start}"


@dataclass
class EvidenceSpan:
    evidence_id: str
    doc_id: str
    chunk_id: str
    title: str
    evidence_type: str
    text: str
    page_start: int | None
    page_end: int | None
    element_ids: list[str] = field(default_factory=list)
    bbox: list[float] | None = None
    section_path: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentGraph:
    doc_id: str
    title: str
    path: str
    pages: list[PageRecord] = field(default_factory=list)
    blocks: list[BlockRecord] = field(default_factory=list)
    evidence_spans: list[EvidenceSpan] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def to_jsonable(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, list):
        return [to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: to_jsonable(v) for k, v in value.items()}
    return value

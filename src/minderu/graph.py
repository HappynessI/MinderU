from __future__ import annotations

from minderu.schema import BlockRecord, Chunk, DocumentGraph, DocumentRecord, EvidenceSpan, PageRecord


def build_document_graphs(docs: list[DocumentRecord], chunks: list[Chunk]) -> list[DocumentGraph]:
    chunks_by_doc: dict[str, list[Chunk]] = {}
    for chunk in chunks:
        chunks_by_doc.setdefault(chunk.doc_id, []).append(chunk)
    return [_build_graph(doc, chunks_by_doc.get(doc.doc_id, [])) for doc in docs]


def _build_graph(doc: DocumentRecord, chunks: list[Chunk]) -> DocumentGraph:
    elements_by_id = {element.element_id: element for element in doc.elements}
    page_map: dict[int, PageRecord] = {}
    blocks: list[BlockRecord] = []
    evidence: list[EvidenceSpan] = []

    for element in doc.elements:
        blocks.append(
            BlockRecord(
                block_id=element.element_id,
                doc_id=element.doc_id,
                type=element.type,
                text=element.text,
                page_start=element.page_start,
                page_end=element.page_end,
                bbox=element.bbox,
                section_path=element.section_path,
                metadata=element.metadata,
            )
        )
        for page in _page_range(element.page_start, element.page_end):
            page_map.setdefault(page, PageRecord(doc_id=doc.doc_id, page=page)).element_ids.append(element.element_id)

    for chunk in chunks:
        source_elements = [elements_by_id[element_id] for element_id in chunk.element_ids if element_id in elements_by_id]
        bbox = next((element.bbox for element in source_elements if element.bbox), None)
        metadata = dict(chunk.metadata)
        metadata.setdefault("source_element_types", sorted({element.type for element in source_elements}))
        evidence.append(
            EvidenceSpan(
                evidence_id=chunk.chunk_id,
                doc_id=chunk.doc_id,
                chunk_id=chunk.chunk_id,
                title=chunk.title,
                evidence_type=str(metadata.get("evidence_type") or chunk.chunk_type),
                text=chunk.text,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                element_ids=chunk.element_ids,
                bbox=bbox,
                section_path=chunk.section_path,
                metadata=metadata,
            )
        )
        for page in _page_range(chunk.page_start, chunk.page_end):
            page_map.setdefault(page, PageRecord(doc_id=doc.doc_id, page=page)).chunk_ids.append(chunk.chunk_id)

    pages = [page_map[page] for page in sorted(page_map)]
    return DocumentGraph(
        doc_id=doc.doc_id,
        title=doc.title,
        path=doc.path,
        pages=pages,
        blocks=blocks,
        evidence_spans=evidence,
        metadata=doc.metadata,
    )


def _page_range(page_start: int | None, page_end: int | None) -> range:
    if page_start is None:
        return range(0)
    end = page_end or page_start
    return range(page_start, end + 1)

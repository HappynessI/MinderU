from __future__ import annotations

from pathlib import Path
from typing import Any

from minderu.indexing.hybrid import _as_float_list, _load_sentence_transformer
from minderu.schema import Chunk
from minderu.utils import write_jsonl


def export_qdrant_points(
    chunks: list[Chunk],
    output_path: str | Path,
    collection: str = "minderu_documents",
    embedding_model: str | None = None,
) -> Path:
    vectors = _encode_vectors(chunks, embedding_model) if embedding_model else None
    rows = []
    for idx, chunk in enumerate(chunks):
        row: dict[str, Any] = {
            "collection": collection,
            "id": chunk.chunk_id,
            "payload": _payload(chunk),
        }
        if vectors is not None:
            row["vector"] = vectors[idx]
        rows.append(row)
    out = Path(output_path)
    write_jsonl(out, rows)
    return out


def _encode_vectors(chunks: list[Chunk], embedding_model: str) -> list[list[float]]:
    model = _load_sentence_transformer(embedding_model)
    if model is None:
        raise RuntimeError("embedding_model is required for vector export")
    texts = [str(chunk.metadata.get("semantic_repr") or chunk.text) for chunk in chunks]
    return [_as_float_list(vector) for vector in model.encode(texts, convert_to_tensor=False, show_progress_bar=False)]


def _payload(chunk: Chunk) -> dict[str, Any]:
    return {
        "chunk_id": chunk.chunk_id,
        "doc_id": chunk.doc_id,
        "title": chunk.title,
        "text": chunk.text,
        "chunk_type": chunk.chunk_type,
        "evidence_type": chunk.metadata.get("evidence_type", chunk.chunk_type),
        "page_start": chunk.page_start,
        "page_end": chunk.page_end,
        "element_ids": chunk.element_ids,
        "section_path": chunk.section_path,
        "metadata": chunk.metadata,
    }

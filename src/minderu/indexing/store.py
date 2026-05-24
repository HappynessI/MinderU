from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from minderu.indexing.bm25 import BM25Index
from minderu.schema import Chunk, DocumentRecord, Element
from minderu.utils import read_json, write_json


def build_index(docs: list[DocumentRecord], chunks: list[Chunk], output_dir: str | Path) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    index_path = out / "index.json"
    write_json(
        index_path,
        {
            "version": 1,
            "documents": [asdict(doc) for doc in docs],
            "chunks": [asdict(chunk) for chunk in chunks],
        },
    )
    return index_path


def _document_from_dict(row: dict[str, Any]) -> DocumentRecord:
    elements = [Element(**e) for e in row.get("elements", [])]
    return DocumentRecord(
        doc_id=row["doc_id"],
        title=row["title"],
        path=row["path"],
        pages=row.get("pages", 0),
        elements=elements,
        metadata=row.get("metadata", {}),
    )


def load_index(path: str | Path) -> tuple[list[DocumentRecord], list[Chunk], BM25Index]:
    payload = read_json(path)
    docs = [_document_from_dict(d) for d in payload.get("documents", [])]
    chunks = [Chunk(**c) for c in payload.get("chunks", [])]
    return docs, chunks, BM25Index(chunks)


from __future__ import annotations

from pathlib import Path
from typing import Any

from minderu.schema import DocumentRecord, Element
from minderu.utils import read_json, stable_id


def _block_text(block: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("table_caption", "image_caption", "img_caption", "caption"):
        value = block.get(key)
        if isinstance(value, list):
            parts.extend(str(item).strip() for item in value if str(item).strip())
        elif isinstance(value, str) and value.strip():
            parts.append(value.strip())
    for key in ("text", "content", "html", "table_body", "table_html", "md", "markdown"):
        value = block.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    if isinstance(block.get("spans"), list):
        span_text = "".join(str(span.get("content", span.get("text", ""))) for span in block["spans"]).strip()
        if span_text:
            parts.append(span_text)
    for key in ("img_path", "image_path", "image_url"):
        value = block.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(f"[image: {value.strip()}]")
    return "\n\n".join(dict.fromkeys(parts))


def _block_type(block: dict[str, Any]) -> str:
    raw = str(block.get("type") or block.get("category") or block.get("block_type") or "text").lower()
    if "table" in raw or block.get("table_body") or block.get("table_html"):
        return "table"
    if "image" in raw or "figure" in raw or block.get("img_path") or block.get("image_path"):
        return "figure"
    if "title" in raw:
        return "title"
    return raw or "text"


def _page_number(block: dict[str, Any]) -> int | None:
    if "page_idx" in block:
        try:
            return int(block["page_idx"]) + 1
        except (TypeError, ValueError):
            return None
    for key in ("page", "page_id", "page_no", "page_num"):
        if key not in block:
            continue
        try:
            value = int(block[key])
        except (TypeError, ValueError):
            return None
        return value if value >= 1 else value + 1
    return None


def _iter_content_blocks(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [b for b in payload if isinstance(b, dict)]
    if isinstance(payload, dict):
        for key in ("content", "blocks", "elements", "layout_dets", "pdf_info"):
            value = payload.get(key)
            if isinstance(value, list):
                if key == "pdf_info":
                    blocks: list[dict[str, Any]] = []
                    for page_idx, page in enumerate(value, start=1):
                        if isinstance(page, dict):
                            for name in ("para_blocks", "blocks", "layout_dets"):
                                for block in page.get(name, []) or []:
                                    if isinstance(block, dict):
                                        block = dict(block)
                                        block.setdefault("page_idx", page_idx - 1)
                                        blocks.append(block)
                    return blocks
                return [b for b in value if isinstance(b, dict)]
    return []


def load_mineru_document(json_path: str | Path, source_pdf: str | Path | None = None) -> DocumentRecord:
    path = Path(json_path)
    payload = read_json(path)
    blocks = _iter_content_blocks(payload)
    title = Path(source_pdf).stem if source_pdf else path.stem
    doc_id = stable_id(str((Path(source_pdf) if source_pdf else path).resolve()))
    pages = 0
    doc = DocumentRecord(
        doc_id=doc_id,
        title=title,
        path=str(source_pdf or json_path),
        pages=pages,
        metadata={"parser": "mineru_json", "mineru_json": str(path), "has_bbox": True},
    )
    for idx, block in enumerate(blocks):
        text = _block_text(block)
        if not text:
            continue
        page_num = _page_number(block)
        if page_num:
            pages = max(pages, page_num)
        bbox = block.get("bbox") or block.get("poly")
        doc.elements.append(
            Element(
                element_id=stable_id(doc_id, "mineru", str(idx), text[:40]),
                doc_id=doc_id,
                type=_block_type(block),
                text=text,
                page_start=page_num,
                page_end=page_num,
                bbox=bbox if isinstance(bbox, list) else None,
                metadata={k: v for k, v in block.items() if k not in {"text", "content", "html", "md", "markdown", "spans"}},
            )
        )
    doc.pages = pages
    return doc

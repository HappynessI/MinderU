from __future__ import annotations

import re
from pathlib import Path

from minderu.schema import DocumentRecord, Element
from minderu.utils import normalize_space, run_command, stable_id


FIGURE_RE = re.compile(
    r"^\s*((图|表)\s*\d+|(?:Fig\.?|Figure|Table)\s*\d+|TABLE\s*\d+)\b[:：.\s-]*(.*)",
    re.IGNORECASE,
)


def _pdf_pages(path: Path) -> int:
    try:
        out = run_command(["pdfinfo", str(path)]).stdout
    except Exception:
        return 0
    for line in out.splitlines():
        if line.startswith("Pages:"):
            return int(line.split(":", 1)[1].strip())
    return 0


def _page_text(path: Path, page: int) -> str:
    try:
        return run_command(["pdftotext", "-layout", "-f", str(page), "-l", str(page), str(path), "-"]).stdout
    except Exception:
        return ""


def _looks_like_table_line(line: str) -> bool:
    if len(line.strip()) < 18:
        return False
    multi_spaces = len(re.findall(r" {2,}", line))
    digits = len(re.findall(r"\d", line))
    return multi_spaces >= 2 and (digits >= 2 or len(line.split()) >= 5)


def _extract_table_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if _looks_like_table_line(line):
            current.append(line.rstrip())
        else:
            if len(current) >= 3:
                blocks.append("\n".join(current))
            current = []
    if len(current) >= 3:
        blocks.append("\n".join(current))
    return blocks


def _extract_captions(text: str) -> list[tuple[str, str]]:
    captions: list[tuple[str, str]] = []
    for raw in text.splitlines():
        m = FIGURE_RE.match(raw.strip())
        if m:
            label = m.group(1).strip()
            captions.append((label, raw.strip()))
    return captions


def parse_pdf_with_poppler(path: str | Path) -> DocumentRecord:
    pdf_path = Path(path)
    pages = _pdf_pages(pdf_path)
    doc_id = stable_id(str(pdf_path.resolve()))
    doc = DocumentRecord(
        doc_id=doc_id,
        title=pdf_path.stem,
        path=str(pdf_path),
        pages=pages,
        metadata={"parser": "poppler_pdftotext", "has_bbox": False},
    )

    for page in range(1, pages + 1):
        raw = _page_text(pdf_path, page)
        text = normalize_space(raw)
        if not text:
            continue
        doc.elements.append(
            Element(
                element_id=stable_id(doc_id, "page", str(page)),
                doc_id=doc_id,
                type="page_text",
                text=text,
                page_start=page,
                page_end=page,
            )
        )
        for idx, block in enumerate(_extract_table_blocks(raw)):
            doc.elements.append(
                Element(
                    element_id=stable_id(doc_id, "table", str(page), str(idx)),
                    doc_id=doc_id,
                    type="table_text",
                    text=normalize_space(block),
                    page_start=page,
                    page_end=page,
                    metadata={"source": "layout_text_heuristic"},
                )
            )
        for idx, (label, caption) in enumerate(_extract_captions(raw)):
            elem_type = "table_caption" if label.lower().startswith("table") or label.startswith("表") else "figure_caption"
            doc.elements.append(
                Element(
                    element_id=stable_id(doc_id, "caption", str(page), str(idx), label),
                    doc_id=doc_id,
                    type=elem_type,
                    text=caption,
                    page_start=page,
                    page_end=page,
                    metadata={"label": label},
                )
            )
    return doc


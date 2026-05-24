from __future__ import annotations

import re

from minderu.schema import Chunk, DocumentRecord, Element
from minderu.utils import stable_id


EN_SECTION_RE = re.compile(
    r"^\s*(abstract|objectives?|background|methods?|results?|conclusions?|introduction|materials and methods|discussion|references)\b[:：.]?\s*(.*)$",
    re.IGNORECASE,
)
CN_SECTION_RE = re.compile(r"^\s*(摘要|目的|方法|结果|结论|问题[一二三四五六七八九十\d]+[、.．]|[一二三四五六七八九十\d]+[、.．])\s*(.*)$")
NUMBERED_RE = re.compile(r"^\s*(\d+(?:\.\d+){0,2})[.)、．]\s+(.{2,80})$")


def _heading(line: str) -> str | None:
    s = line.strip()
    if not s or len(s) > 120:
        return None
    m = EN_SECTION_RE.match(s)
    if m:
        tail = m.group(2).strip()
        return f"{m.group(1).title()}: {tail}" if tail else m.group(1).title()
    m = CN_SECTION_RE.match(s)
    if m:
        return s
    m = NUMBERED_RE.match(s)
    if m:
        return s
    if s.isupper() and 4 <= len(s) <= 80 and len(s.split()) <= 8:
        return s.title()
    return None


def _split_paragraphs(text: str) -> list[str]:
    text = text.replace("\r\n", "\n")
    parts = re.split(r"\n\s*\n|(?<=。)\s*(?=问题[一二三四五六七八九十\d]+[、.．])", text)
    out: list[str] = []
    for part in parts:
        lines = [ln.rstrip() for ln in part.splitlines() if ln.strip()]
        if lines:
            out.append("\n".join(lines))
    return out


def _pack_units(units: list[str], max_chars: int) -> list[str]:
    chunks: list[str] = []
    buf: list[str] = []
    size = 0
    for unit in units:
        if buf and size + len(unit) > max_chars:
            chunks.append("\n\n".join(buf))
            buf = []
            size = 0
        buf.append(unit)
        size += len(unit)
    if buf:
        chunks.append("\n\n".join(buf))
    return chunks


def _contextual_text(title: str, section_path: list[str], body: str) -> str:
    context = [f"Document: {title}"]
    if section_path:
        context.append("Section: " + " > ".join(section_path[-3:]))
    return "\n".join(context) + "\n\n" + body.strip()


def _chunk_element(doc: DocumentRecord, element: Element, max_chars: int) -> list[Chunk]:
    if element.type in {"table", "table_text", "table_caption", "figure", "figure_caption"}:
        text = _contextual_text(doc.title, element.section_path, element.text)
        return [
            Chunk(
                chunk_id=stable_id(doc.doc_id, element.element_id, "atomic"),
                doc_id=doc.doc_id,
                title=doc.title,
                text=text,
                chunk_type=element.type,
                page_start=element.page_start,
                page_end=element.page_end,
                element_ids=[element.element_id],
                section_path=element.section_path,
                metadata=dict(element.metadata),
            )
        ]

    units = _split_paragraphs(element.text)
    packed = _pack_units(units, max_chars=max_chars)
    chunks: list[Chunk] = []
    for idx, text in enumerate(packed):
        chunks.append(
            Chunk(
                chunk_id=stable_id(doc.doc_id, element.element_id, str(idx)),
                doc_id=doc.doc_id,
                title=doc.title,
                text=_contextual_text(doc.title, element.section_path, text),
                chunk_type="text",
                page_start=element.page_start,
                page_end=element.page_end,
                element_ids=[element.element_id],
                section_path=element.section_path,
                metadata={},
            )
        )
    return chunks


def annotate_sections(doc: DocumentRecord) -> None:
    section_stack: list[str] = []
    for element in doc.elements:
        first_lines = [ln.strip() for ln in element.text.splitlines()[:8] if ln.strip()]
        for line in first_lines:
            h = _heading(line)
            if not h:
                continue
            if h.lower().startswith(("abstract", "objectives", "background", "methods", "results", "conclusions")):
                section_stack = [h]
            elif h.startswith("问题") or NUMBERED_RE.match(h):
                section_stack = [h]
            elif len(section_stack) > 2:
                section_stack = section_stack[:-1] + [h]
            else:
                section_stack = [h]
            break
        element.section_path = list(section_stack)


def chunk_document(doc: DocumentRecord, max_chars: int = 1800) -> list[Chunk]:
    annotate_sections(doc)
    chunks: list[Chunk] = []
    for element in doc.elements:
        chunks.extend(_chunk_element(doc, element, max_chars=max_chars))
    return chunks


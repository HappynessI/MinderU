from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import asdict
from typing import Any

from minderu.schema import Chunk


TOKEN_RE = re.compile(r"[A-Za-z]+(?:[-_][A-Za-z]+)*|\d+(?:\.\d+)?|[\u4e00-\u9fff]|[Δδ∆±%/]+|[A-Za-z]*\d+[A-Za-z]*")

QUERY_ALIASES = {
    "摘要": " abstract objectives background methods results conclusions",
    "结果": " results outcome outcomes endpoint end point",
    "方法": " methods",
    "结论": " conclusions",
    "表格": " table",
    "表": " table",
    "图": " fig figure",
    "诊断流程图": " diagnostic flowchart algorithm",
    "答案": " answer",
    "医学指标": " ci cardiac index l/min m2 ⌬ci ΔCI",
}


def tokenize(text: str) -> list[str]:
    tokens = [m.group(0).lower() for m in TOKEN_RE.finditer(text)]
    # Add lightweight CJK bigrams to make Chinese phrase retrieval less sparse.
    cjk = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    for seq in cjk:
        tokens.extend(seq[i : i + 2] for i in range(len(seq) - 1))
    return tokens


class BM25Index:
    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        self.doc_tokens = [tokenize(c.text) for c in chunks]
        self.doc_lens = [len(t) for t in self.doc_tokens]
        self.avgdl = sum(self.doc_lens) / max(1, len(self.doc_lens))
        self.term_freqs = [Counter(toks) for toks in self.doc_tokens]
        df: Counter[str] = Counter()
        for toks in self.doc_tokens:
            df.update(set(toks))
        n = max(1, len(chunks))
        self.idf = {term: math.log(1 + (n - freq + 0.5) / (freq + 0.5)) for term, freq in df.items()}
        self.label_pages = self._build_label_pages()

    def _build_label_pages(self) -> dict[str, set[tuple[str, int]]]:
        pages: dict[str, set[tuple[str, int]]] = {}
        label_re = re.compile(r"(?:table|fig(?:ure)?|图|表)\s*([0-9一二三四五六七八九十]+)", re.I)
        line_label_re = re.compile(r"^\s*(?:table|fig(?:ure)?|图|表)\s*([0-9一二三四五六七八九十]+)", re.I | re.M)
        for idx, chunk in enumerate(self.chunks):
            if chunk.page_start is None:
                continue
            label_source = " ".join(str(v) for v in chunk.metadata.values() if isinstance(v, str))
            searchable_text = f"{chunk.text}\n{label_source}"
            if "caption" in chunk.chunk_type:
                matches = list(label_re.finditer(searchable_text))
            else:
                matches = list(line_label_re.finditer(searchable_text))
            for match in matches:
                num = match.group(1)
                raw = match.group(0).lower().replace(" ", "")
                for label in self._label_aliases(raw, num):
                    pages.setdefault(label, set()).add((chunk.doc_id, chunk.page_start))

            # OCR sometimes splits "TABLE" and "5. ..." into adjacent chunks.
            # Rejoin those lightweight label fragments so the table body page can be boosted.
            if idx + 1 >= len(self.chunks):
                continue
            nxt = self.chunks[idx + 1]
            if nxt.doc_id != chunk.doc_id or nxt.page_start != chunk.page_start:
                continue
            body = _body_text(chunk.text).strip().lower()
            next_body = _body_text(nxt.text).strip()
            if body in {"table", "figure", "fig", "图", "表"}:
                m = re.match(r"([0-9一二三四五六七八九十]+)[.、．]?\s+", next_body)
                if m:
                    raw = f"{body}{m.group(1)}"
                    for label in self._label_aliases(raw, m.group(1)):
                        pages.setdefault(label, set()).add((chunk.doc_id, chunk.page_start))
        return pages

    @staticmethod
    def _label_aliases(raw: str, num: str) -> set[str]:
        labels = {raw}
        if raw.startswith("fig") or raw.startswith("figure") or raw.startswith("图"):
            labels.update({f"fig{num}", f"figure{num}", f"图{num}"})
        if raw.startswith("table") or raw.startswith("表"):
            labels.update({f"table{num}", f"表{num}"})
        return labels

    def search(
        self,
        query: str,
        top_k: int = 8,
        source_hint: str | None = None,
        page_hint: int | None = None,
    ) -> list[dict[str, Any]]:
        expanded_query = query + "".join(extra for key, extra in QUERY_ALIASES.items() if key in query)
        q_terms = tokenize(expanded_query)
        scores: list[tuple[float, int]] = []
        query_lower = query.lower()
        wants_table = "table" in query_lower or "表格" in query or re.search(r"(?<!图)表\s*[0-9一二三四五六七八九十]?", query)
        wants_figure = "图" in query or "figure" in query_lower or "fig" in query_lower
        mixed_visual_table = bool(wants_table and wants_figure)
        source_hint_lower = source_hint.lower() if source_hint else None
        label_match = re.search(r"(?:table|fig(?:ure)?|图|表)\s*([0-9一二三四五六七八九十]+)", query, re.I)
        label_texts: list[str] = []
        if label_match:
            num = label_match.group(1)
            prefix = label_match.group(0).lower()
            label_texts.append(prefix.replace(" ", ""))
            if "图" in prefix:
                label_texts.extend([f"fig{num}", f"figure{num}"])
                if "表格" in query or "表" in query:
                    label_texts.append(f"table{num}")
            if "表" in prefix:
                label_texts.extend([f"table{num}"])
        if mixed_visual_table:
            label_texts = [label for label in label_texts if label.startswith("table") or label.startswith("表")]
        for idx, tf in enumerate(self.term_freqs):
            chunk = self.chunks[idx]
            if source_hint_lower:
                title_path = (chunk.title + " " + str(chunk.metadata.get("path", ""))).lower()
                if source_hint_lower not in title_path and PathSafe.basename(source_hint_lower) not in title_path:
                    continue
            if page_hint is not None:
                if chunk.page_start is None:
                    continue
                if not (chunk.page_start <= page_hint <= (chunk.page_end or chunk.page_start)):
                    # Keep adjacent chunks for page-spanning section answers.
                    if abs(chunk.page_start - page_hint) > 1:
                        continue
            score = 0.0
            dl = self.doc_lens[idx] or 1
            for term in q_terms:
                if term not in tf:
                    continue
                freq = tf[term]
                denom = freq + self.k1 * (1 - self.b + self.b * dl / max(self.avgdl, 1e-6))
                score += self.idf.get(term, 0.0) * (freq * (self.k1 + 1)) / denom
            chunk_text_lower = chunk.text.lower()
            if wants_table:
                if "table" in chunk.chunk_type or "table" in chunk_text_lower or "表" in chunk.text:
                    score *= 1.35
                if "table" in chunk.chunk_type:
                    score += 10.0
            if wants_figure and not mixed_visual_table:
                if "figure" in chunk.chunk_type or "图" in chunk.text or "fig" in chunk_text_lower:
                    score *= 1.35
                if "figure" in chunk.chunk_type:
                    score += 8.0
            elif mixed_visual_table and "figure" in chunk.chunk_type:
                score *= 0.75
            if "摘要" in query or "abstract" in query_lower:
                if "abstract" in chunk_text_lower or "摘要" in chunk.text:
                    score *= 1.2
                if chunk.page_start == 1:
                    score += 20.0
                if "结果" in query and "results" in chunk_text_lower and re.search(r"(ci|cardiac index|⌬ci|δci|ΔCI|l/min)", chunk.text, re.I):
                    score += 20.0
            if label_texts:
                compact = chunk_text_lower.replace(" ", "")
                if any(label in compact for label in label_texts):
                    score += 12.0
                elif any(label.replace("figure", "fig") in compact for label in label_texts):
                    score += 8.0
                on_label_page = chunk.page_start is not None and any(
                    (chunk.doc_id, chunk.page_start) in self.label_pages.get(label, set())
                    for label in label_texts
                )
                if on_label_page:
                    if "table" in chunk.chunk_type or "table" in query_lower or "表" in query:
                        score += 45.0 if mixed_visual_table else 28.0
                        if mixed_visual_table and chunk.chunk_type == "table_text":
                            score += 20.0
                    else:
                        score += 8.0
            if page_hint is not None and chunk.page_start == page_hint:
                score *= 1.25
            if score > 0:
                scores.append((score, idx))
        scores.sort(reverse=True)
        return [
            {
                "score": round(score, 6),
                "chunk": asdict(self.chunks[idx]),
            }
            for score, idx in scores[:top_k]
        ]


class PathSafe:
    @staticmethod
    def basename(value: str) -> str:
        value = value.replace("\\", "/")
        return value.rsplit("/", 1)[-1].removesuffix(".pdf")


def _body_text(text: str) -> str:
    return re.sub(r"^(?:Document|Section): .+\n", "", text, flags=re.M).strip()

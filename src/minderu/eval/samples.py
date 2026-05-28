from __future__ import annotations

from pathlib import Path
from typing import Any

from minderu.indexing.store import load_index
from minderu.qa import answer_question
from minderu.rerank import expected_evidence_type
from minderu.utils import write_json, write_jsonl
from minderu.xlsx_reader import read_first_sheet


def evaluate_sample_questions(
    index_path: str | Path,
    xlsx_path: str | Path,
    output_dir: str | Path,
    use_source_hints: bool = False,
    retriever: str = "bm25",
    embedding_model: str | None = None,
) -> list[dict[str, Any]]:
    _, _, index = load_index(index_path, retriever=retriever, embedding_model=embedding_model)
    rows = read_first_sheet(xlsx_path)
    results: list[dict[str, Any]] = []
    for row in rows:
        question = row.get("输入", "")
        source_hint = _source_hint(row) if use_source_hints else None
        response = answer_question(index, question, top_k=6, source_hint=source_hint)
        expected_source = row.get("来源", "")
        metrics = _ranking_metrics(expected_source, question, response["citations"])
        results.append(
            {
                "id": row.get("id"),
                "question": question,
                "expected": row.get("输出", ""),
                "source": row.get("来源", ""),
                "source_hint": source_hint,
                "blind_source_hit_top3": metrics["source_hit_at_3"],
                "metrics": metrics,
                "note": row.get("说明", ""),
                "answer": response["answer"],
                "citations": response["citations"],
            }
        )
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "sample_eval.json", results)
    write_jsonl(out / "sample_eval.jsonl", results)
    with (out / "sample_eval.md").open("w", encoding="utf-8") as f:
        f.write("# 医疗样例问答评测\n\n")
        f.write(f"- 模式：{'source-hinted demo' if use_source_hints else 'blind retrieval'}\n\n")
        f.write(f"- 检索器：{retriever}{' + dense=' + embedding_model if embedding_model else ''}\n\n")
        summary = _summarize_metrics(results)
        f.write("## 汇总指标\n\n")
        f.write(f"- Source Hit@1：{summary['source_hit_at_1']:.3f}\n")
        f.write(f"- Source Hit@3：{summary['source_hit_at_3']:.3f}\n")
        f.write(f"- Source Hit@5：{summary['source_hit_at_5']:.3f}\n")
        f.write(f"- Evidence Type Hit@3：{summary['evidence_type_hit_at_3']:.3f}\n")
        if summary["page_hint_count"]:
            f.write(f"- Page Hit@3：{summary['page_hit_at_3']:.3f} ({int(summary['page_hint_count'])} page-hinted samples)\n")
        f.write(f"- MRR：{summary['mrr']:.3f}\n\n")
        for item in results:
            f.write(f"## {item['id']}. {item['question']}\n\n")
            f.write(f"- 期望来源：{item['source']}\n")
            f.write(f"- Top-3 来源命中：{item['blind_source_hit_top3']}\n")
            f.write(f"- 样例说明：{item['note']}\n\n")
            f.write("### 系统回答\n\n")
            f.write(item["answer"] + "\n\n")
            f.write("### 证据\n\n")
            for cite in item["citations"][:3]:
                f.write(f"- {cite['title']} p.{cite['page_start']} score={cite['score']} type={cite['chunk_type']}\n")
            f.write("\n")
    return results


def _source_hint(row: dict[str, str]) -> str:
    for key in ("来源", "输出"):
        value = row.get(key, "")
        if value.lower().endswith(".pdf") or ".pdf" in value.lower():
            return value
    return row.get("来源", "")


def _source_hit(expected_source: str, titles: list[str]) -> bool:
    if not expected_source:
        return False
    expected = expected_source.lower().removesuffix(".pdf")
    return any(expected in title.lower() or title.lower() in expected for title in titles)


def _ranking_metrics(expected_source: str, question: str, citations: list[dict[str, Any]]) -> dict[str, float | bool | int | None]:
    titles = [cite["title"] for cite in citations]
    rank = _source_rank(expected_source, titles)
    expected_type = expected_evidence_type(question)
    page_hint = _page_hint(question)
    return {
        "source_rank": rank,
        "source_hit_at_1": rank is not None and rank <= 1,
        "source_hit_at_3": rank is not None and rank <= 3,
        "source_hit_at_5": rank is not None and rank <= 5,
        "expected_evidence_type": expected_type,
        "evidence_type_hit_at_3": _type_hit(expected_type, citations[:3]),
        "page_hint": page_hint,
        "page_hit_at_3": _page_hit(page_hint, citations[:3]),
        "reciprocal_rank": 0.0 if rank is None else 1.0 / rank,
    }


def _source_rank(expected_source: str, titles: list[str]) -> int | None:
    if not expected_source:
        return None
    expected = expected_source.lower().removesuffix(".pdf")
    for idx, title in enumerate(titles, start=1):
        lowered = title.lower()
        if expected in lowered or lowered in expected:
            return idx
    return None


def _summarize_metrics(results: list[dict[str, Any]]) -> dict[str, float]:
    if not results:
        return {
            "source_hit_at_1": 0.0,
            "source_hit_at_3": 0.0,
            "source_hit_at_5": 0.0,
            "evidence_type_hit_at_3": 0.0,
            "page_hit_at_3": 0.0,
            "page_hint_count": 0.0,
            "mrr": 0.0,
        }
    metrics = [row["metrics"] for row in results]
    n = len(metrics)
    typed = [item for item in metrics if item["expected_evidence_type"]]
    page_hinted = [item for item in metrics if item["page_hint"] is not None]
    return {
        "source_hit_at_1": sum(1 for item in metrics if item["source_hit_at_1"]) / n,
        "source_hit_at_3": sum(1 for item in metrics if item["source_hit_at_3"]) / n,
        "source_hit_at_5": sum(1 for item in metrics if item["source_hit_at_5"]) / n,
        "evidence_type_hit_at_3": 0.0 if not typed else sum(1 for item in typed if item["evidence_type_hit_at_3"]) / len(typed),
        "page_hit_at_3": 0.0 if not page_hinted else sum(1 for item in page_hinted if item["page_hit_at_3"]) / len(page_hinted),
        "page_hint_count": float(len(page_hinted)),
        "mrr": sum(float(item["reciprocal_rank"]) for item in metrics) / n,
    }


def _page_hint(question: str) -> int | None:
    import re

    match = re.search(r"第\s*(\d+)\s*页", question)
    return int(match.group(1)) if match else None


def _type_hit(expected_type: str | None, citations: list[dict[str, Any]]) -> bool | None:
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


def _page_hit(page_hint: int | None, citations: list[dict[str, Any]]) -> bool | None:
    if page_hint is None:
        return None
    for cite in citations:
        page_start = cite.get("page_start")
        page_end = cite.get("page_end") or page_start
        if page_start is not None and page_start <= page_hint <= page_end:
            return True
    return False

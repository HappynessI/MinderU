from __future__ import annotations

from pathlib import Path
from typing import Any

from minderu.indexing.store import load_index
from minderu.qa import answer_question
from minderu.utils import write_json, write_jsonl
from minderu.xlsx_reader import read_first_sheet


def evaluate_sample_questions(
    index_path: str | Path,
    xlsx_path: str | Path,
    output_dir: str | Path,
    use_source_hints: bool = False,
) -> list[dict[str, Any]]:
    _, _, index = load_index(index_path)
    rows = read_first_sheet(xlsx_path)
    results: list[dict[str, Any]] = []
    for row in rows:
        question = row.get("输入", "")
        source_hint = _source_hint(row) if use_source_hints else None
        response = answer_question(index, question, top_k=6, source_hint=source_hint)
        expected_source = row.get("来源", "")
        top_titles = [cite["title"] for cite in response["citations"][:3]]
        results.append(
            {
                "id": row.get("id"),
                "question": question,
                "expected": row.get("输出", ""),
                "source": row.get("来源", ""),
                "source_hint": source_hint,
                "blind_source_hit_top3": _source_hit(expected_source, top_titles),
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

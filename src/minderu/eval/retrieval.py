from __future__ import annotations

from pathlib import Path
from typing import Any

from minderu.eval.metrics import ranking_metrics, summarize_metrics
from minderu.indexing.store import load_index
from minderu.qa import answer_question
from minderu.utils import read_json, write_json, write_jsonl
from minderu.xlsx_reader import read_first_sheet


def evaluate_retrieval(
    index_path: str | Path,
    output_dir: str | Path,
    samples_xlsx: str | Path | None = None,
    samples_jsonl: str | Path | None = None,
    use_source_hints: bool = False,
    retriever: str = "bm25",
    embedding_model: str | None = None,
    reranker: str = "rules",
    reranker_model: str | None = None,
    rerank_pool: int = 50,
    hit_ks: tuple[int, ...] = (1, 3, 5),
) -> list[dict[str, Any]]:
    _, _, index = load_index(index_path, retriever=retriever, embedding_model=embedding_model)
    rows = _load_rows(samples_xlsx, samples_jsonl)
    top_k = max(hit_ks)
    results: list[dict[str, Any]] = []
    for row in rows:
        question = _question(row)
        source_hint = _source(row) if use_source_hints else None
        response = answer_question(
            index,
            question,
            top_k=top_k,
            source_hint=source_hint,
            reranker=reranker,
            reranker_model=reranker_model,
            rerank_pool=rerank_pool,
        )
        metrics = ranking_metrics(
            _source(row),
            question,
            response["citations"],
            hit_ks=hit_ks,
            expected_page=_expected_page(row),
            expected_type=_expected_type(row),
        )
        results.append(
            {
                "id": row.get("id") or row.get("qid"),
                "question": question,
                "source": _source(row),
                "source_hint": source_hint,
                "expected_page": _expected_page(row),
                "expected_evidence_type": _expected_type(row),
                "metrics": metrics,
                "citations": response["citations"],
                "evidence_packages": response.get("evidence_packages", []),
            }
        )

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    summary = summarize_metrics(results, hit_ks=hit_ks)
    write_json(out / "retrieval_eval.json", {"summary": summary, "results": results})
    write_jsonl(out / "retrieval_eval.jsonl", results)
    _write_markdown(out / "retrieval_eval.md", results, summary, retriever, embedding_model, hit_ks)
    return results


def _load_rows(samples_xlsx: str | Path | None, samples_jsonl: str | Path | None) -> list[dict[str, Any]]:
    if samples_xlsx:
        return read_first_sheet(samples_xlsx)
    if samples_jsonl:
        rows = []
        with Path(samples_jsonl).open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(read_json_line(line))
        return rows
    raise ValueError("one of samples_xlsx or samples_jsonl is required")


def read_json_line(line: str) -> dict[str, Any]:
    import json

    value = json.loads(line)
    if not isinstance(value, dict):
        raise ValueError("JSONL rows must be objects")
    return value


def _question(row: dict[str, Any]) -> str:
    return str(row.get("question") or row.get("输入") or "").strip()


def _source(row: dict[str, Any]) -> str:
    return str(row.get("source") or row.get("来源") or "").strip()


def _expected_page(row: dict[str, Any]) -> int | None:
    value = row.get("page") or row.get("expected_page")
    if value in (None, ""):
        return None
    return int(value)


def _expected_type(row: dict[str, Any]) -> str | None:
    value = row.get("evidence_type") or row.get("expected_evidence_type")
    return str(value) if value else None


def _write_markdown(
    path: Path,
    results: list[dict[str, Any]],
    summary: dict[str, float],
    retriever: str,
    embedding_model: str | None,
    hit_ks: tuple[int, ...],
) -> None:
    with path.open("w", encoding="utf-8") as f:
        f.write("# Retrieval Evaluation\n\n")
        f.write(f"- Retriever: {retriever}{' + dense=' + embedding_model if embedding_model else ''}\n")
        f.write(f"- Samples: {len(results)}\n\n")
        f.write("## Summary\n\n")
        for k in hit_ks:
            f.write(f"- Source Hit@{k}: {summary[f'source_hit_at_{k}']:.3f}\n")
        f.write(f"- MRR: {summary['mrr']:.3f}\n")
        for k in hit_ks:
            f.write(f"- Evidence Type Hit@{k}: {summary[f'evidence_type_hit_at_{k}']:.3f}\n")
        if summary["page_hint_count"]:
            for k in hit_ks:
                f.write(f"- Page Hit@{k}: {summary[f'page_hit_at_{k}']:.3f}\n")
        f.write("\n## Queries\n\n")
        for item in results:
            f.write(f"### {item['id']}. {item['question']}\n\n")
            f.write(f"- Source: {item['source']}\n")
            f.write(f"- Source rank: {item['metrics']['source_rank']}\n")
            f.write("- Top evidence:\n")
            for cite in item["citations"][:3]:
                f.write(f"  - {cite['title']} p.{cite['page_start']} type={cite['evidence_type']} score={cite['score']}\n")
            f.write("\n")

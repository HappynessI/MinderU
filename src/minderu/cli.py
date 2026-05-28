from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from minderu.api.server import serve
from minderu.chunking import chunk_document
from minderu.eval.samples import evaluate_sample_questions
from minderu.indexing.store import build_index, load_index
from minderu.parsers import load_mineru_document, parse_pdf_with_poppler
from minderu.qa import answer_question
from minderu.schema import DocumentRecord
from minderu.utils import list_input_files, write_json


def _find_mineru_json(pdf: Path, mineru_dir: Path | None) -> Path | None:
    if mineru_dir is None:
        return None
    candidates = [
        mineru_dir / pdf.stem / "auto" / f"{pdf.stem}_content_list.json",
        mineru_dir / pdf.stem / f"{pdf.stem}_content_list.json",
        mineru_dir / f"{pdf.stem}_content_list.json",
        mineru_dir / f"{pdf.stem}.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def ingest(args: argparse.Namespace) -> None:
    input_path = Path(args.input)
    output_dir = Path(args.output)
    mineru_dir = Path(args.mineru_dir) if args.mineru_dir else None
    pdfs = list_input_files(input_path, (".pdf",))
    if not pdfs:
        raise SystemExit(f"No PDFs found under {input_path}")

    docs: list[DocumentRecord] = []
    all_chunks = []
    parsed_dir = output_dir / "parsed"
    for pdf in pdfs:
        mineru_json = _find_mineru_json(pdf, mineru_dir)
        if mineru_json:
            doc = load_mineru_document(mineru_json, source_pdf=pdf)
        else:
            doc = parse_pdf_with_poppler(pdf)
        chunks = chunk_document(doc, max_chars=args.max_chars)
        docs.append(doc)
        all_chunks.extend(chunks)
        write_json(parsed_dir / f"{doc.doc_id}.document.json", asdict(doc))
        write_json(parsed_dir / f"{doc.doc_id}.chunks.json", [asdict(c) for c in chunks])
        print(f"parsed {pdf.name}: pages={doc.pages} elements={len(doc.elements)} chunks={len(chunks)}")

    index_path = build_index(docs, all_chunks, output_dir)
    print(f"index written: {index_path}")


def query(args: argparse.Namespace) -> None:
    _, _, index = load_index(args.index, retriever=args.retriever, embedding_model=args.embedding_model)
    result = answer_question(index, args.question, top_k=args.top_k, source_hint=args.source_hint)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    print(result["answer"])
    print("\nSources:")
    for cite in result["citations"][: args.top_k]:
        page = cite["page_start"] if cite["page_start"] is not None else "?"
        print(f"- {cite['title']} p.{page} score={cite['score']} type={cite['chunk_type']}")


def evaluate(args: argparse.Namespace) -> None:
    results = evaluate_sample_questions(
        args.index,
        args.samples_xlsx,
        args.output,
        use_source_hints=args.use_source_hints,
        retriever=args.retriever,
        embedding_model=args.embedding_model,
    )
    print(f"evaluated {len(results)} questions -> {args.output}")


def inspect(args: argparse.Namespace) -> None:
    docs, chunks, _ = load_index(args.index)
    print(f"documents={len(docs)} chunks={len(chunks)}")
    by_type: dict[str, int] = {}
    for chunk in chunks:
        by_type[chunk.chunk_type] = by_type.get(chunk.chunk_type, 0) + 1
    for key in sorted(by_type):
        print(f"{key}: {by_type[key]}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="minderu")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("ingest", help="Parse PDFs and build a local traceable RAG index.")
    p.add_argument("--input", required=True, help="PDF file or directory.")
    p.add_argument("--output", required=True, help="Output knowledge-base directory.")
    p.add_argument("--mineru-dir", default=None, help="Optional MinerU output directory containing content_list JSON files.")
    p.add_argument("--max-chars", type=int, default=1800, help="Maximum semantic chunk size.")
    p.set_defaults(func=ingest)

    p = sub.add_parser("query", help="Run extractive QA over a built index.")
    p.add_argument("--index", required=True)
    p.add_argument("--question", required=True)
    p.add_argument("--top-k", type=int, default=6)
    p.add_argument("--source-hint", default=None)
    p.add_argument("--retriever", choices=("bm25", "hybrid"), default="bm25")
    p.add_argument("--embedding-model", default=None, help="Optional sentence-transformers model for dense retrieval.")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=query)

    p = sub.add_parser("eval", help="Evaluate the provided medical sample XLSX questions.")
    p.add_argument("--index", required=True)
    p.add_argument("--samples-xlsx", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--use-source-hints", action="store_true", help="Use expected source column as a document filter for demo mode.")
    p.add_argument("--retriever", choices=("bm25", "hybrid"), default="bm25")
    p.add_argument("--embedding-model", default=None, help="Optional sentence-transformers model for dense retrieval.")
    p.set_defaults(func=evaluate)

    p = sub.add_parser("inspect", help="Print index statistics.")
    p.add_argument("--index", required=True)
    p.set_defaults(func=inspect)

    p = sub.add_parser("api", help="Start the zero-dependency HTTP API.")
    p.add_argument("--index", required=True)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--retriever", choices=("bm25", "hybrid"), default="bm25")
    p.add_argument("--embedding-model", default=None, help="Optional sentence-transformers model for dense retrieval.")
    p.set_defaults(func=lambda a: serve(a.index, a.host, a.port, retriever=a.retriever, embedding_model=a.embedding_model))
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()

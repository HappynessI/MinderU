# Submission Checklist

Use this checklist before packaging MinderU for the medical literature RAG competition.

## Required Materials

- Source code: repository root with `src/minderu`, `scripts`, `tests`, and `pyproject.toml`.
- System overview: `README.md`.
- Technical solution: `docs/TECHNICAL_SOLUTION.md`.
- API documentation: `docs/API.md`.
- Deployment instructions: `docs/DEPLOYMENT.md`.
- Sample evaluation summary: `docs/SAMPLE_EVAL_SUMMARY.md`.

## Optional Materials

- Short slide deck describing the problem, pipeline, evidence traceability, and sample results.
- Demo video showing ingest, Web Demo, `/query`, and citation output.
- MinerU-enhanced evaluation report if MinerU JSON/OCR outputs are available.

## Pre-Submission Validation

```bash
cd /Data/wyh/MinderU
PYTHONPATH=src python3 -m unittest discover -s tests -v
scripts/run_sample_pipeline.sh
```

Confirm:

- `/health` returns `{"ok": true}`.
- `/query` returns an answer and non-empty citations.
- Blind retrieval and source-hinted reports are regenerated under `data/runs/sample_kb/`.
- No generated `data/runs/`, `data/MedBench_*`, PDF, cache, log, or virtualenv files are staged.

## Git Hygiene

Recommended commit split:

1. `docs: add competition API and submission materials`
2. `fix: improve visual table retrieval for medical samples`

Before committing:

```bash
git status --short
git diff -- README.md docs src tests
```

Do not commit large benchmark datasets or local run artifacts.


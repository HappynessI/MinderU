# 样例评测摘要

生成时间：本地运行 `scripts/run_sample_pipeline.sh`。

## 环境

- Python：系统 `python3`
- PDF 工具：`pdfinfo`、`pdftotext`
- Python 额外依赖：无

## 命令

```bash
cd /Data/wyh/MinderU
scripts/run_sample_pipeline.sh
```

## 结果文件

- `data/runs/sample_kb/index.json`
- `data/runs/sample_kb/eval/sample_eval.md`
- `data/runs/sample_kb/eval/sample_eval.json`
- `data/runs/sample_kb/eval/sample_eval.jsonl`

## 当前能力边界

Poppler fallback 可以验证端到端 RAG 和来源追溯，但不是最终解析质量上限。图像内部文字、复杂扫描表格、bbox 级定位应使用 MinerU JSON/OCR/VLM 输出增强。


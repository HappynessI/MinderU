# 样例评测摘要

生成时间：本地运行 `scripts/run_sample_pipeline.sh`。

## 环境

- Python：系统 `python3`
- PDF 工具：`pdfinfo`、`pdftotext`
- Python 额外依赖：无
- 评测模式：默认 blind retrieval，不使用样例来源列过滤文档

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
- `data/runs/sample_kb/eval_source_hinted/sample_eval.md`

## 当前能力边界

Poppler fallback 可以验证端到端 RAG 和来源追溯，但不是最终解析质量上限。图像内部文字、复杂扫描表格、bbox 级定位应使用 MinerU JSON/OCR/VLM 输出增强。

Blind retrieval 用于检查问题本身能否召回正确文献；source-hinted demo 用于模拟产品中用户已经选中文献后的问答。二者不应混为一个指标。

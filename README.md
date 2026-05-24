# MinderU 医疗文献高质量 RAG 知识库

MinderU 面向“基于 MinerU 的医疗文献高质量知识库（RAG）”赛题，提供从医疗 PDF 到可追溯问答的端到端原型：

```text
PDF / MinerU JSON -> 结构化元素 -> 医学语义切片 -> 本地索引 -> 检索问答 -> API / 评测报告
```

第一版默认零重依赖运行：只要求系统已有 `pdfinfo` / `pdftotext`。如果已有 MinerU 输出，可通过 `--mineru-dir` 接入 `content_list.json`，保留更完整的表格、图片、bbox 和阅读顺序信息。

## 快速运行

```bash
cd /Data/wyh/MinderU
export PYTHONPATH="$PWD/src"

python -m minderu.cli ingest \
  --input "医疗赛题/相关样例" \
  --output data/runs/sample_kb

python -m minderu.cli eval \
  --index data/runs/sample_kb/index.json \
  --samples-xlsx "医疗赛题/相关样例/医疗文档问答示例 - MinerU.xlsx" \
  --output data/runs/sample_kb/eval
```

也可以直接运行：

```bash
scripts/run_sample_pipeline.sh
```

## 查询示例

```bash
python -m minderu.cli query \
  --index data/runs/sample_kb/index.json \
  --source-hint seyfarth2008.pdf \
  --question "请根据输入的文献内容，提取摘要中的结果部分内容"
```

启动 API：

```bash
python -m minderu.cli api --index data/runs/sample_kb/index.json --host 127.0.0.1 --port 8000
curl -s http://127.0.0.1:8000/health
curl -s -X POST http://127.0.0.1:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"question":"提取第2页问题四的答案","source_hint":"子宫内膜异位症超声评估中国专家共识.pdf"}'
```

## 已覆盖能力

- 复杂版面：按页解析双栏/多栏文本，并用表格/图注启发式补充结构元素。
- MinerU 接入：支持读取 MinerU JSON，将其统一到本项目 schema。
- 语义切片：识别摘要、Results、Methods、中文“问题一/二/三/四”等医学文献结构，不按固定字数硬切。
- 可追溯检索：每个 chunk 保留文献名、页码、元素类型、section path、element id。
- 样例评测：自动读取赛事样例 Excel，输出 `sample_eval.md/json/jsonl`。
- 零依赖 API：基于标准库 HTTP server 暴露 `/health` 和 `/query`。

## 参考依据

设计参考了 MinerU、OmniDocBench、Docling 和医疗 RAG 的公开工作：

- MinerU：PDF/Office/Image 到 Markdown/JSON，强调阅读顺序、表格 HTML、图片/图注、OCR 和 FastAPI。
- OmniDocBench：以 Markdown/JSON 评测端到端文档解析，关注 text/table/formula/layout/reading order。
- Docling：统一文档表示、表格结构识别和面向生成式 AI 的文档转换。
- 医疗 RAG：强调证据链、来源追溯、结构化医学概念和跨文献一致性。

更完整方案见 [docs/TECHNICAL_SOLUTION.md](docs/TECHNICAL_SOLUTION.md)。

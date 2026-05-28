# MinderU 医疗文献高质量 RAG 知识库

MinderU 面向“基于 MinerU 的医疗文献高质量知识库（RAG）”赛题，提供从医疗 PDF 到可追溯问答的端到端原型：

```text
PDF / MinerU JSON -> 结构化元素 -> 医学语义切片 -> 本地索引 -> 检索问答 -> Web Demo / API / 评测报告
```

第一版默认零重依赖运行：只要求系统已有 `pdfinfo` / `pdftotext`。如果已有 MinerU 输出，可通过 `--mineru-dir` 接入 `content_list.json`，保留更完整的表格、图片、bbox 和阅读顺序信息。

## 开源地址与技术方案

本项目已在 GitHub 开源，仓库地址为：<https://github.com/HappynessI/MinderU>。

完整技术解决方案文档位于 [docs/TECHNICAL_SOLUTION.md](docs/TECHNICAL_SOLUTION.md)，其中包含系统架构、解析与切片策略、检索/问答方案、API 部署方式、评测结果和后续增强路线。

## 快速运行

```bash
cd /Data/wyh/MinderU
export PYTHONPATH="$PWD/src"

python3 -m minderu.cli ingest \
  --input "医疗赛题/相关样例" \
  --output data/runs/sample_kb

python3 -m minderu.cli eval \
  --index data/runs/sample_kb/index.json \
  --samples-xlsx "医疗赛题/相关样例/医疗文档问答示例 - MinerU.xlsx" \
  --output data/runs/sample_kb/eval
```

默认评测是 blind retrieval，不使用 Excel 的“来源”列过滤文档。若要演示“用户已选中文献后问答”的产品模式，可追加 `--use-source-hints`。

也可以直接运行：

```bash
scripts/run_sample_pipeline.sh
```

脚本会生成两个评测目录：`eval/` 为 blind retrieval，`eval_source_hinted/` 为用户已选中文献后的演示模式。

## 查询示例

```bash
python3 -m minderu.cli query \
  --index data/runs/sample_kb/index.json \
  --source-hint seyfarth2008.pdf \
  --question "请根据输入的文献内容，提取摘要中的结果部分内容" \
  --answer-mode grounded
```

可选启用 hybrid 检索骨架：

```bash
python3 -m minderu.cli query \
  --index data/runs/sample_kb/index.json \
  --retriever hybrid \
  --reranker rules \
  --question "请根据输入的文献内容，提取图5中的表格数据"
```

若安装了 `sentence-transformers`，可通过 `--embedding-model` 增加 dense retrieval，并与 BM25 通过 RRF 融合：

```bash
python3 -m minderu.cli query \
  --index data/runs/sample_kb/index.json \
  --retriever hybrid \
  --embedding-model paraphrase-multilingual-MiniLM-L12-v2 \
  --reranker cross-encoder \
  --reranker-model cross-encoder/ms-marco-MiniLM-L-6-v2 \
  --question "请根据输入的文献内容，提取摘要中的结果部分内容"
```

独立检索评测：

```bash
python3 -m minderu.cli eval-retrieval \
  --index data/runs/sample_kb/index.json \
  --samples-xlsx "医疗赛题/相关样例/医疗文档问答示例 - MinerU.xlsx" \
  --output data/runs/sample_kb/retrieval_eval \
  --top-k-values 1,3,5
```

导出 Qdrant 导入用 JSONL：

```bash
python3 -m minderu.cli export-qdrant \
  --index data/runs/sample_kb/index.json \
  --output data/runs/sample_kb/qdrant_points.jsonl \
  --collection minderu_documents
```

启动 Web Demo / API：

```bash
python3 -m minderu.cli api --index data/runs/sample_kb/index.json --answer-mode grounded --host 127.0.0.1 --port 8000
curl -s http://127.0.0.1:8000/health
curl -s -X POST http://127.0.0.1:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"question":"提取第2页问题四的答案","source_hint":"子宫内膜异位症超声评估中国专家共识.pdf","answer_mode":"grounded"}'
```

浏览器打开 `http://127.0.0.1:8000/` 即可使用简约风格 Web Demo。Demo 会从 `/documents` 读取当前知识库文献列表，并通过 `/query` 返回答案、citations 和 evidence packages。

## 已覆盖能力

- 复杂版面：按页解析双栏/多栏文本，并用表格/图注启发式补充结构元素。
- MinerU 接入：支持读取 MinerU JSON，将其统一到本项目 schema。
- 语义切片：识别摘要、Results、Methods、中文“问题一/二/三/四”等医学文献结构，不按固定字数硬切。
- 可追溯检索：每个 chunk 保留文献名、页码、元素类型、section path、element id。
- 混合检索骨架：支持 BM25 + 可选 dense embedding + RRF；无 dense 依赖时自动回退 BM25。
- 证据打包：`/query` 返回 chunk citations 和 evidence packages，便于展示表格/图像/同页证据组。
- Grounded 回答：支持 `extractive`、`grounded` 和 `evidence_only` 三种 answer mode，其中 grounded 模式强制输出 `[E#]` 引用。
- 证据资产：支持 `/tables/{evidence_id}` 返回表格资产，`/assets/{evidence_id}/image` 返回已入库图像资产。
- 向量库交付：支持导出 Qdrant-compatible JSONL，可选择附带 dense embedding。
- 检索评测：独立输出 Source Hit@k、Evidence Type Hit@k、Page Hit@k 和 MRR。
- 样例评测：自动读取赛事样例 Excel，输出 `sample_eval.md/json/jsonl`。
- 盲评模式：默认不使用样例来源列作为检索过滤，报告 Top-3 来源命中。
- 零依赖 Web/API：基于标准库 HTTP server 提供 `/`、`/health`、`/documents` 和 `/query`。

## 提交材料

- API 文档：[docs/API.md](docs/API.md)
- 部署说明：[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
- 技术方案：[docs/TECHNICAL_SOLUTION.md](docs/TECHNICAL_SOLUTION.md)
- 样例评测摘要：[docs/SAMPLE_EVAL_SUMMARY.md](docs/SAMPLE_EVAL_SUMMARY.md)
- 提交检查清单：[docs/SUBMISSION_CHECKLIST.md](docs/SUBMISSION_CHECKLIST.md)
- 高端方案路线图：[docs/HIGH_END_SOLUTION_ROADMAP.md](docs/HIGH_END_SOLUTION_ROADMAP.md)

如果 MedBench 申请后提供了固定请求/响应协议，应在现有 `/query` 能力外补一个轻量 adapter endpoint，保持核心 RAG 管线不变。

## 参考依据

设计参考了 MinerU、OmniDocBench、Docling 和医疗 RAG 的公开工作：

- MinerU：PDF/Office/Image 到 Markdown/JSON，强调阅读顺序、表格 HTML、图片/图注、OCR 和 FastAPI。
- OmniDocBench：以 Markdown/JSON 评测端到端文档解析，关注 text/table/formula/layout/reading order。
- Docling：统一文档表示、表格结构识别和面向生成式 AI 的文档转换。
- 医疗 RAG：强调证据链、来源追溯、结构化医学概念和跨文献一致性。

更完整方案见 [docs/TECHNICAL_SOLUTION.md](docs/TECHNICAL_SOLUTION.md)。

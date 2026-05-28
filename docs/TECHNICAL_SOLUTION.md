# 技术解决方案

## 1. 目标

赛题要求解决医疗 PDF 在 RAG 知识库构建中的三个问题：

1. 复杂版式和语义级解析困难。
2. 固定字数切片破坏医学章节逻辑。
3. 从 PDF 到知识库缺少端到端自动化。

MinderU 的目标是做一条可部署、可评测、可扩展的医疗文献 RAG 管线，并让每条回答都能追溯到文献、页码和结构元素。

## 2. 相关优秀工作如何被吸收

### MinerU

MinerU 官方能力包括 PDF/图片/Office 到 Markdown/JSON、阅读顺序恢复、表格 HTML、图片/图注、公式、OCR、FastAPI/Gradio 等。MinderU 不重复实现 MinerU 的模型能力，而是把 MinerU 输出作为优先输入格式：`src/minderu/parsers/mineru.py` 会读取 `content_list.json` 或 middle JSON 风格结构，并转成本项目统一 schema。

当前无 MinerU 运行环境时，系统退化到 `pdftotext -layout`，仍保留页码、表格启发式、图注检测和可追溯检索。这让 Demo 在干净服务器上也能跑通。

### OmniDocBench

OmniDocBench 的核心启发是：文档解析不应只看纯文本，而要同时评估阅读顺序、标题、正文、表格、图注、页脚、公式等元素。MinderU schema 因此保留：

- `element.type`：`page_text`、`table_text`、`table_caption`、`figure_caption` 等。
- `page_start/page_end`：来源页。
- `bbox`：MinerU 提供时保留。
- `section_path`：章节路径。

这些字段直接进入 RAG metadata，避免检索阶段丢失版面和结构信息。

### Docling

Docling 的统一文档表示和面向 GenAI 的导出思想被用于本项目的数据层：解析器只负责把不同来源统一成 `DocumentRecord -> Element -> Chunk`，后续索引、API、评测不关心 PDF 解析后端。未来可以新增 Docling adapter，而无需改检索和问答逻辑。

### 医疗 RAG

医疗 RAG 的关键不是“生成得像”，而是证据可靠。MinderU 第一版采用抽取式回答，避免无证据生成；每个答案返回 citations。后续可以在 citations 之上接入 LLM 做带引用摘要，但生成器不得绕过检索证据。

## 3. 系统架构

```text
Input
  PDF files
  MinerU JSON outputs

Parsing
  MinerU adapter
  Poppler fallback parser

Normalization
  DocumentRecord
  Element
  Chunk

Chunking
  Heading-aware medical semantic chunking
  Atomic table/figure chunks
  Parent context injected into chunk text

Indexing
  Local JSON artifact
  BM25 lexical index
  Optional dense embedding index
  RRF hybrid fusion
  Optional future Qdrant layer

Serving
  CLI
  Minimal Web Demo
  Zero-dependency HTTP API
  Sample evaluator
```

## 4. 关键实现路径

### 4.1 解析

- 首选 MinerU JSON：保留 bbox、表格 HTML、图片路径、图注、标题等结构。
- 兜底 Poppler：逐页调用 `pdftotext -layout`，解析页文本。
- 表格启发式：检测多列空格、数字密集的连续行，作为 `table_text`。
- 图表标题：识别 `图 3`、`Table 1`、`TABLE 5`、`Fig. 1` 等。

代码位置：

- `src/minderu/parsers/mineru.py`
- `src/minderu/parsers/pdf_text.py`

### 4.2 医学语义切片

不是按固定字数直接切分，而是先识别章节信号：

- 英文：`Objectives`、`Background`、`Methods`、`Results`、`Conclusions`。
- 中文：`摘要`、`目的`、`方法`、`结果`、`结论`、`问题一/二/三/四`。
- 编号标题：`1.`、`2.`、`3.1`。

表格、图注作为原子 chunk，不被段落拼接切碎。

代码位置：

- `src/minderu/chunking/semantic.py`

### 4.3 检索

第一版实现了本地 BM25，并新增 hybrid retrieval 骨架。默认无外部依赖时仍使用 BM25；如果提供 `--embedding-model`，系统会加载 `sentence-transformers`，执行 dense retrieval，并用 RRF 与 BM25 结果融合。BM25 层做了医学样例需要的增强：

- 中英查询扩展：`摘要 -> abstract/results/conclusions`，`表格 -> table`，`图 -> fig/figure`。
- 图表编号增强：`图5中的表格数据` 会同时匹配 `Figure 5` 和 `Table 5`。
- source hint：Demo 中“当前输入文献”作为过滤条件，避免跨文献误召回。
- page hint：识别“第 2 页”并优先对应页。

代码位置：

- `src/minderu/indexing/bm25.py`

后续增强：

- 使用医学/多语言 embedding 模型进行 dense retrieval，例如 multilingual MiniLM、BGE-M3 或医学领域 embedding。
- 使用 Qdrant payload filter 存储 `doc_id/page/section/type`。
- 加 BM25 + dense + reranker 的三段式混合检索。

### 4.4 问答

第一版采用抽取式问答：

- 优先返回目标结构片段，例如摘要 Results、问题四、表格 chunk。
- 对图像/流程图返回图注、页码和说明，提示需要 MinerU OCR/VLM 或页面截图补全图像内容。
- 所有答案返回 citations，不做无来源扩写。

代码位置：

- `src/minderu/qa/extractive.py`

## 5. 样例评测结果

运行：

```bash
scripts/run_sample_pipeline.sh
```

默认样例评测采用 blind retrieval，不把 Excel 中的“来源”列传给检索器。`scripts/run_sample_pipeline.sh` 同时输出 `eval_source_hinted/`，该目录使用 `--use-source-hints`，仅用于演示用户已选中文献后的问答模式。

输出：

- `data/runs/sample_kb/index.json`
- `data/runs/sample_kb/eval/sample_eval.md`
- `data/runs/sample_kb/eval/sample_eval.json`
- `data/runs/sample_kb/eval/sample_eval.jsonl`

当前样例覆盖：

| id | 类型 | 当前结果 |
| --- | --- | --- |
| 1 | 中文指南图 3 流程图 | 定位到 Stanford B 型主动脉夹层文献第 5 页图注；完整图像内容需 MinerU OCR/VLM |
| 2 | 英文横向长表 Table 1 | 定位到 shchelochkov2019 的 Table 1 相关表格 chunk |
| 3 | 老旧扫描/表 5 | 定位到 todo1992 的 TABLE 5 相关表格证据 |
| 4 | 水印遮挡中文指南第 2 页问题四 | 抽取到“磨玻璃样回声”、CDFI、囊壁/分隔血流等关键内容 |
| 5 | 英文摘要 Results 医学指标 | 抽取到 `CI`、`l/min/m2`、`p = 0.02`、30-day mortality 等结果 |

## 6. 工程化说明

- 无网络、无模型依赖时可以跑通全链路。
- Web Demo 使用标准库 HTTP server 直接托管 `src/minderu/web/index.html`，访问 `/` 或 `/demo` 即可打开；前端通过 `/documents` 读取文献列表，通过 `/query` 查询答案和证据。
- 大文件和产物不进入 git：`data/runs/`、`data/outputs/` 已忽略。
- 远端仓库已配置为 `git@github.com:HappynessI/MinderU.git`。
- 当前 API 不依赖 FastAPI；如需生产部署，可把 `api/server.py` 包装成 FastAPI 服务。
- API、部署和提交清单分别维护在 `docs/API.md`、`docs/DEPLOYMENT.md` 和 `docs/SUBMISSION_CHECKLIST.md`，用于比赛提交和平台适配。
- 高端方案路线图维护在 `docs/HIGH_END_SOLUTION_ROADMAP.md`，当前代码已开始落地其中的 hybrid retrieval 和 evidence metadata 基础。

## 6.1 当前提交边界

当前系统是医疗文献 RAG 交付，不是通用医疗大模型或通用 Agent。它适合回答“已入库文献中的内容抽取、表格/图注定位、摘要结果提取、页码可追溯问答”等任务；若 MedBench 使用通用 LLM/Agent benchmark，需要额外接入大模型推理或工具调用规划层。

`source_hint` 只用于“用户已选中文献后提问”的产品形态。无文献提示的 blind retrieval 是系统检索能力评估，不应与 source-hinted demo 混成一个指标。

## 7. 后续增强建议

1. 接入真实 MinerU 解析结果，替换 Poppler fallback，用 bbox 和图片资产解决图 3 流程图完整提取。
2. 增加表格结构化后处理，把 `table_text` 转成二维 cell JSON。
3. 增加 Qdrant 混合检索和医学 embedding 模型。
4. 增加 LLM 引用生成层，但必须强制 citation-grounded。
5. 增加 OmniDocBench 风格解析指标：文本编辑距离、表格 TEDS、阅读顺序、图表标题匹配率。

## 8. 参考链接

- MinerU 官方文档：https://opendatalab.github.io/MinerU/
- MinerU GitHub：https://github.com/opendatalab/MinerU
- MinerU paper：https://arxiv.org/abs/2409.18839
- OmniDocBench GitHub：https://github.com/opendatalab/OmniDocBench
- OmniDocBench paper：https://arxiv.org/abs/2412.07626
- Docling GitHub：https://github.com/docling-project/docling
- Docling technical report：https://research.ibm.com/publications/docling-technical-report
- Medical Graph RAG：https://aclanthology.org/2025.acl-long.1381.pdf

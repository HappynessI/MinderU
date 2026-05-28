# MinderU-Pro 高端方案路线图

本文档记录 MinderU 面向“基于 MinerU 的医疗文献高质量知识库 RAG”赛题的高端可包装方案。目标不是提交一个 BM25 baseline，而是把项目升级为“结构化医学文献解析 + 多表示检索 + 精排 + 可追溯生成 + 双层评测”的端到端系统。

## 1. 项目定位

MinderU-Pro 定位为医疗文献智能知识工程系统，解决临床指南、系统综述、临床试验论文、病例研究等 PDF 文献进入 RAG 知识库时的三个核心问题：

1. 复杂版式还原：双栏、多栏、横向表格、图文混排、扫描件、水印遮挡、图表编号错位。
2. 医学语义切片：按文献逻辑、医学研究结构和证据单元切分，而不是固定长度切块。
3. 可信问答交付：每个回答绑定文献、页码、bbox、元素 id、表格/图片资产，支持审计和复核。

一句话包装：

> MinderU-Pro 是一个 MinerU-first 的医疗文献 RAG 知识库构建系统，面向高可信医疗问答，提供结构化解析、混合检索、证据精排和引用约束生成能力。

## 2. 参考依据

本方案参考以下公开论文和工程实践：

- MinerU：`content_list.json` 以阅读顺序保存可读内容块，并包含 block type、`page_idx`、`bbox` 等字段，适合作为文档结构化入口。  
  https://opendatalab.github.io/MinerU/reference/output_files/
- MinerU paper：强调 PDF/OCR/layout/formula/table 等复杂内容抽取和后处理规则。  
  https://arxiv.org/abs/2409.18839
- OmniDocBench：用 text/table/formula/layout/reading order 等指标评估文档解析，不只看最终问答。  
  https://arxiv.org/abs/2412.07626
- OmniDocBench GitHub：提供文档解析评测思路和 leaderboard 维度。  
  https://github.com/opendatalab/OmniDocBench
- Docling：统一文档表示，支持 PDF 到 JSON/Markdown，并包含表格结构导出能力，可作为第二解析后端或对照验证。  
  https://docling-project.github.io/docling/v2/
- Qdrant multi-representation search：支持 dense/sparse/multi-vector 与 metadata filter，适合医疗 RAG 的多表示检索。  
  https://qdrant.tech/documentation/tutorials-search-engineering/multi-representation-search/
- Sentence-Transformers retrieve-rerank：bi-encoder 召回 + cross-encoder 精排是成熟 RAG 检索范式。  
  https://github.com/huggingface/sentence-transformers/blob/main/docs/cross_encoder/usage/usage.rst

## 3. 当前 baseline 与目标差距

当前 MinderU 已经具备端到端原型：

- PDF/MinerU JSON 到统一 schema。
- 医学结构感知 chunking。
- BM25 检索和规则 boost。
- 抽取式回答和 citations。
- Web Demo/API/样例评测。

但它仍是 baseline：

- Poppler fallback 仍是默认可跑路径，复杂表格和图片信息损失大。
- 检索以 BM25 为主，缺少 dense semantic retrieval 和 reranker。
- 表格、图像、正文还没有形成多表示索引。
- 评测以样例问答来源命中为主，缺少文档解析质量指标。
- 回答层是抽取式，没有 citation-grounded LLM synthesis。

目标版本要从“可运行 demo”升级到“可参赛包装的高端系统”。

## 4. 目标架构

```text
Input
  PDF / scanned PDF / MinerU output / Docling output

Parsing Layer
  MinerU-first adapter
  Docling fallback adapter
  Poppler emergency fallback

Document Graph
  Document
  Page
  Block
  Section
  Table
  Figure
  Citation
  EvidenceSpan

Representation Layer
  plain text
  markdown
  table html / table markdown / table cell json
  figure caption / page crop / image path
  bbox and reading order metadata

Chunking Layer
  section-aware chunks
  table-as-evidence chunks
  figure-as-evidence chunks
  parent-child chunks
  query-time expansion context

Indexing Layer
  BM25 sparse index
  dense embedding index
  metadata index
  optional Qdrant backend

Retrieval Layer
  query classifier
  sparse retrieval
  dense retrieval
  metadata/page/type filter
  RRF fusion
  cross-encoder rerank

Answer Layer
  extractive answer
  citation-grounded LLM synthesis
  table/figure evidence rendering
  abstention when evidence is weak

Evaluation Layer
  retrieval metrics
  answer metrics
  parsing metrics
  audit report

API/Demo
  /query
  /documents
  /evidence/{id}
  /pages/{doc_id}/{page}
  /tables/{id}
  Web demo with evidence panel
```

## 5. 核心创新点

### 5.1 MinerU-first 医疗文献结构图

不把 MinerU 输出简单转成纯文本，而是转成可查询的 document graph：

- `Document`：文献级 metadata。
- `Page`：页码、尺寸、页面图片。
- `Block`：MinerU block，保留 type、text、bbox、reading order。
- `Section`：医学章节路径，如 Abstract、Methods、Results、Primary outcome、问题四。
- `Table`：表格 html、markdown、cell json、caption、关联正文。
- `Figure`：图像路径、caption、页面 crop、关联正文。
- `EvidenceSpan`：最终回答可引用的最小证据单元。

这样做的价值：

- 检索时可以按 `doc_id/page/type/section` 过滤。
- 回答时可以返回 bbox 和页面截图。
- 评测时可以分别评估文本、表格、图像和阅读顺序。

### 5.2 医学语义切片

切片策略从“固定长度 chunk”升级为“医学证据单元 chunk”：

- 研究论文：Abstract、Methods、Results、Discussion、Primary outcome、Secondary outcome、Subgroup analysis。
- 临床指南：问题一/二/三/四、推荐意见、证据等级、适用人群、禁忌证。
- 表格：表 caption + 表头 + 行组 + 邻近解释正文。
- 图像：图 caption + 图所在页上下文 + image/page crop。
- 长段落：parent-child chunk，召回子 chunk，回答时带父级上下文。

### 5.3 多表示混合检索

每个证据单元保存多种 representation：

- `text_repr`：干净正文，用于 BM25 和 dense。
- `semantic_repr`：加入标题、section、caption 的语义检索文本。
- `table_repr`：Markdown table / cell json flatten。
- `visual_repr`：figure caption + nearby text + page image reference。
- `metadata_repr`：doc title、page、block type、section path、label。

检索流程：

1. Query classifier 判断问题类型：摘要、表格、图像、页码、指南问题、跨文献比较。
2. BM25 sparse retrieval 召回精确术语、表号、页码、医学指标。
3. Dense retrieval 召回语义相似内容。
4. Metadata filter 根据 `source_hint/page/type/section` 约束候选。
5. RRF 融合 sparse/dense/metadata-ranked 列表。
6. Cross-encoder reranker 对 top-50 精排。
7. Evidence packer 组装 top evidence，去重、合并相邻 chunk。

### 5.4 Citation-grounded 生成

回答层分两种模式：

- `extractive`：直接抽取证据片段，适合表格、结果段、指南原文。
- `synthesis`：LLM 只基于 evidence pack 生成答案，输出必须带 citation id。

生成约束：

- 不允许引用 evidence pack 外内容。
- 证据不足时返回“不足以回答”。
- 每个结论至少绑定一个 citation。
- 表格/图像问题优先返回结构化 evidence，而不是自由发挥。

### 5.5 解析与 RAG 双层评测

比赛包装不能只说“问答看起来对”。需要双层指标：

解析层：

- Text edit distance。
- Table structure similarity，参考 TEDS 思路。
- Reading order edit distance。
- Figure/table caption match。
- Bbox/page grounding accuracy。

RAG 层：

- Recall@1/3/5。
- MRR。
- Source hit@k。
- Page hit@k。
- Evidence type accuracy。
- Answer citation coverage。
- Abstention correctness。

## 6. 预计实现模块

### 6.1 `minderu.parsers.mineru_graph`

新增 MinerU-first parser：

- 读取 `content_list.json`。
- 读取可选 `middle.json`。
- 解析 block type、page_idx、bbox、image/table path。
- 输出 `DocumentGraph`。

### 6.2 `minderu.parsers.docling_adapter`

新增可选 Docling adapter：

- 读取 Docling JSON。
- 提取 hierarchy、tables、captions。
- 映射到同一 `DocumentGraph`。

### 6.3 `minderu.chunking.evidence`

新增 evidence chunker：

- section chunk。
- table evidence chunk。
- figure evidence chunk。
- parent-child chunk。
- adjacent chunk merge。

### 6.4 `minderu.indexing.hybrid`

新增 hybrid index：

- 保留当前 BM25。
- 可选 sentence-transformers embedding。
- 本地 dense index 初版可用 numpy cosine。
- 生产版可接 Qdrant。
- 实现 RRF fusion。

### 6.5 `minderu.rerank`

新增 reranker：

- 默认无依赖 fallback：规则 rerank。
- 可选 cross-encoder rerank。
- 输出统一 `EvidenceCandidate`。

### 6.6 `minderu.qa.grounded`

新增 grounded answer：

- evidence pack。
- answer schema。
- citation validation。
- abstention policy。

### 6.7 `minderu.eval`

扩展评测：

- `eval retrieval`：Recall@k、MRR、page hit、type hit。
- `eval parsing`：table/caption/order 指标。
- `eval answer`：citation coverage、source consistency。
- 自动生成 Markdown audit report。

### 6.8 API 扩展

保留现有接口，新增：

- `GET /evidence/{evidence_id}`：返回完整 evidence。
- `GET /documents/{doc_id}/pages/{page}`：返回页面级 evidence 和可选截图。
- `GET /tables/{table_id}`：返回 table markdown/html/cell json。
- `POST /query` 增加 `mode`: `extractive | synthesis | evidence_only`。

## 7. 里程碑

### M1：结构化主干

目标：让系统从 text chunk 升级为 document graph。

- 新增 `DocumentGraph` schema。
- 新增 MinerU-first graph parser。
- 把 table/figure/page/bbox 进入索引 artifact。
- 保持旧 CLI/API 兼容。

验收：

- 样例 PDF 可重新 ingest。
- `index.json` 中有 page/block/table/figure/evidence metadata。
- 当前 5 个样例 source hit 不回退。

### M2：Hybrid Retrieval

目标：从 BM25 baseline 升级为 sparse+dense hybrid。

- 新增 dense embedding 可选依赖。
- 新增 RRF fusion。
- 新增 retrieval metrics。
- 支持 `--retriever bm25|dense|hybrid`。

验收：

- blind retrieval Top-3 不低于当前 5/5。
- 输出 Recall@1/3/5、MRR。
- dense 依赖缺失时自动 fallback 到 BM25。

### M3：Rerank and Evidence Pack

目标：提升首位证据质量，减少“来源对但片段不佳”。

- 新增 cross-encoder reranker 可选路径。
- 新增 evidence packing。
- 去重相邻 chunk。
- 表格/图像问题优先 evidence type 匹配。

验收：

- 第 2/3 题表格 evidence 排名更稳定。
- 第 1 题图像问题返回 figure evidence + page evidence。

### M4：Grounded Answer

目标：从抽取式回答升级为可控生成。

- 接入可选 LLM provider。
- 生成必须引用 evidence id。
- citation validator 拦截无证据结论。
- 支持 `evidence_only` 评测模式。

验收：

- 无 LLM 时仍可运行。
- 有 LLM 时答案更完整但 citation 不丢失。

### M5：Competition Package

目标：形成可展示、可提交、可评测材料。

- 更新技术方案。
- 增加架构图。
- 增加 API demo script。
- 增加样例 audit report。
- 增加 PPT/视频脚本素材。

验收：

- 一条命令跑完整 pipeline。
- 一个 API endpoint 能被 MedBench adapter 调用。
- 文档能清楚说明“为什么不是普通 RAG”。

## 8. Demo 展示卖点

建议演示 4 个场景：

1. 图 3 诊断流程图：展示 figure caption、页码、页面截图/crop、OCR 边界。
2. 横向 Table 1：展示 table markdown/cell json 和表格 evidence。
3. 老旧扫描 Table 5：展示 OCR 拆行修复、hybrid retrieval 和 rerank。
4. 摘要 Results：展示医学指标、单位、p 值、mortality 等信息保持。

展示重点：

- 不是“问答模型猜答案”，而是“文献证据链驱动答案”。
- 不是“PDF 转纯文本”，而是“PDF 转结构化医学证据图”。
- 不是“单 BM25 检索”，而是“多表示检索 + 精排 + 引用约束”。

## 9. 风险与边界

- MinerU 输出质量决定上限，Poppler fallback 只适合 demo 和兜底。
- 表格结构化需要真实 table html/cell 信息，仅靠 layout text 无法稳定恢复复杂表格。
- Cross-encoder 和 LLM 会增加依赖、显存和延迟，必须保持可选。
- 医疗问答必须避免无证据生成，必要时应拒答。
- MedBench API 协议未知，最终需要 adapter 层对齐官方字段。

## 10. 最终交付形态

代码交付：

- `src/minderu/parsers/mineru_graph.py`
- `src/minderu/parsers/docling_adapter.py`
- `src/minderu/chunking/evidence.py`
- `src/minderu/indexing/hybrid.py`
- `src/minderu/rerank/`
- `src/minderu/qa/grounded.py`
- `src/minderu/eval/retrieval.py`
- `src/minderu/eval/parsing.py`

文档交付：

- `README.md`
- `docs/TECHNICAL_SOLUTION.md`
- `docs/HIGH_END_SOLUTION_ROADMAP.md`
- `docs/API.md`
- `docs/DEPLOYMENT.md`
- `docs/SUBMISSION_CHECKLIST.md`
- `docs/SAMPLE_EVAL_SUMMARY.md`

材料交付：

- 演示视频。
- PPT。
- 样例 audit report。
- API 调用示例。

## 11. 推荐实现优先级

最高优先级：

1. MinerU-first document graph。
2. Table/Figure evidence chunk。
3. Hybrid retrieval + RRF。
4. Retrieval metrics。

第二优先级：

1. Cross-encoder rerank。
2. Qdrant backend。
3. Grounded LLM synthesis。
4. Page crop evidence API。

第三优先级：

1. Docling adapter。
2. Full parsing metrics。
3. PPT/video packaging。

最小强版本定义：

> 能读 MinerU JSON，保留表格/图像/bbox，使用 BM25+dense hybrid retrieval 和 RRF，输出 evidence-grounded answer，并给出 Recall@k/MRR/page hit 的评测报告。

## 12. 当前落地进度

已完成第一批代码落地：

- `minderu.indexing.hybrid.HybridIndex`：支持 BM25 + 可选 dense embedding + RRF。没有 `sentence-transformers` 时自动回退 BM25。
- CLI/API/eval 增加 `--retriever bm25|hybrid` 和 `--embedding-model` 参数。
- MinerU parser 进一步保留 `evidence_type`、caption、table html、image path、`page_idx` 等 evidence metadata。
- Chunk metadata 增加 `semantic_repr`，为 dense retrieval、Qdrant payload 和 reranker 做准备。
- 样例评测报告增加 Source Hit@1/3/5 和 MRR。
- 新增 hybrid retrieval 单测，覆盖无 dense fallback 和 dense+RRF 路径。

下一批优先实现：

1. 更完整的 retrieval metrics：page hit、type hit、evidence hit。
2. `DocumentGraph` schema：显式建模 Page/Block/Table/Figure/EvidenceSpan。
3. Evidence packer：合并相邻 chunk，优先保留 table/figure/page evidence。
4. Cross-encoder reranker 可选路径。

# 样例数据说明

本目录保留赛事给出的问答样例 Excel，并在本地开发环境中放置配套 PDF。

PDF 文件体积较大且可能涉及赛事附件分发规则，默认不提交到 git。运行完整样例 pipeline 前，请将以下 PDF 放到本目录：

- `Stanford+B+型主动脉夹层诊断和治疗中国专家共识（2022版）.pdf`
- `seyfarth2008.pdf`
- `shchelochkov2019.pdf`
- `todo1992.pdf`
- `子宫内膜异位症超声评估中国专家共识.pdf`

没有这些 PDF 时，仍可运行单元测试；完整 `scripts/run_sample_pipeline.sh` 需要本地样例 PDF。


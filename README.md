# 金融合规智能审查助手 · LangGraph 参赛工程

基于用户提供的 `金融合规智能审查助手BETA1.0.yml` 迁移，实际使用 LangGraph `StateGraph` 执行节点与条件分支，不通过 Dify 应用接口代理回答。

公网部署请使用 `judge_app.py` 作为入口，它固定启用评委模式，隐藏连接设置。云端 Secrets 模板和具体步骤见 `deploy/`。本地启动仍使用 `app.py`。

## 快速开始

1. Windows 下双击 `启动助手.cmd`，或运行 `powershell -ExecutionPolicy Bypass -File .\start.ps1`。
2. 打开终端显示的本地地址，通常是 http://127.0.0.1:8501 。重复启动会识别并打开已运行的本项目；如端口被其他程序占用，会尝试 8502–8510，不结束其他进程。
3. 左侧输入模型 API key，或将 `.env.example` 复制为 `.env` 后填写 `MODEL_API_KEY`。默认接口 `https://api.deepseek.com`，模型 `deepseek-flash`，温度 0.7。
4. 将原法规资料放入 `knowledge/`；或选择 Dify 原知识库，填写知识库 API key 和真实知识库 UUID。
5. 选择“修正版”，输入具体材料或上传文件，点击“开始审查”。结果可下载为 Markdown，包含参考片段和执行路径。

已有 `.venv` 可直接使用。新机器建议 Python 3.11+；启动脚本在缺少环境时创建虚拟环境并安装 `requirements.txt`。已在本机 Python 3.13.16 环境验证。关闭终端会关闭由启动脚本启动的服务。

## 配置与密钥

`.env`、`api-key.txt`、知识库原文、运行日志均不进入交付源码包。界面输入的密钥仅保留在当前 Streamlit 会话中，不写入报告；本地 `.env` 由用户保管。程序不读取浏览器登录状态。

| 配置 | 说明 |
|---|---|
| MODEL_API_KEY / DEEPSEEK_API_KEY | 模型提供商密钥，环境变量优先于 `.env` |
| MODEL_BASE_URL | Chat Completions 兼容地址；默认 DeepSeek 官方接口 |
| MODEL_NAME | 留空沿用 DSL 节点模型名，默认 deepseek-flash |
| KNOWLEDGE_BACKEND | local / dify |
| KNOWLEDGE_DIR | 本地法规目录；留空使用项目 knowledge 文件夹 |
| DIFY_DATASET_API_KEY | Dify **知识库** API key，不是应用 API key |
| DIFY_DATASET_ID | 知识库真实 UUID，DSL 中的长字符串是导出标识，不能直接用作 API UUID |
| DIFY_SEARCH_METHOD | 留空沿用服务器检索配置；显式设置时传 top_k=4、禁用重排 |
| MODEL_TIMEOUT | 请求超时秒数，默认 120 |
| MAX_INPUT_CHARS | 全部输入文本长度上限，默认 100000，超过会报错，不静默截断 |

若密钥只保存在 Dify 模型供应商后台，需要在本地再次配置，导出 DSL 不含该密钥。

## 五条任务分支

合同审查、产品合规审查、投资范围审查、营销宣传合规审查、一般金融咨询。分类器沿用原系统提示词，条件分支沿用原顺序与 `contains` 判断。分类后进入各自的检索、审查与回复节点。

修正版先解析附件，将用户输入和材料作为完整审查内容；分类器也能看到材料。每次提交独立审查，不将旧材料带入新请求。历史对话仅在当前页面显示，原 DSL 未启用节点对话记忆，因此本版本也不自动添加跨轮记忆。

## 原版与修正版

| 项目 | 原版对照 faithful | 修正版 corrected（默认） |
|---|---|---|
| 合同正文 | 分类器输出的“合同审查” | 用户输入 + 附件原文 |
| 合同知识库上下文 | 文档提取结果，被放在法规参考位置 | 知识检索节点 result |
| 合同检索查询 | 分类名称 | 用户输入 + 材料 |
| 其他三个审查分支附件 | 原提示词不引用附件 | 附件并入审查内容 |
| 一般咨询 | 直接进入 LLM，引用未执行的检索节点，明确报变量缺失 | 补接检索，再传递用户问题 |
| 分类无法匹配 | 原图无默认出口，明确报错 | 进入一般咨询并提示 |
| 防止材料指令干扰 | 不追加提示 | 增加数据与指令区分、证据不足和引用要求 |

原始 YAML 从未修改。修正通过深拷贝后的显式补丁实现，见 `finance_assistant/workflow.py` 的 `prepare_dsl`。迁移器仅支持本导出使用的六种节点类型，不声称支持任意 Dify DSL。原图有两个未接入节点（知识检索5、空的 LLM8）；修正版接入前者，空 LLM8 仍不运行。

“原版对照”保留本 DSL 的数据接线与提示词，不是 Dify 整个平台的逐字复制。Dify 内部上下文序列化、模型插件实现、文件解析和运行错误文案仍可能不同。不能保证随机模型输出逐字一致。

## 知识库与材料边界

- 本地知识库使用中文双字词 + 英文词 BM25 检索，最多 4 个片段，片段标注文件名和字符位置；这与原 Dify 向量检索不同。上传的待审查文件不会自动进入法规库。
- 连接 Dify 模式复用现有知识库服务，尽量保留原知识源；默认保留服务器检索参数，客户端最多取 4 条。DSL 不含底层 embedding、分段、搜索权重与版本，必须另行核对才能验收检索一致性。
- 当前 Dify 检索 API 的 query 限长为 250 字，长查询只发送前 250 字并显式提示；完整正文仍传入审查模型。复杂长材料建议分项审查，后续可加入查询改写与多次召回。
- 不附带虚构的金融法规。空库和无命中都会显示“依据不足”；提示词要求模型不得据此给出确定通过结论。提示词不能构成可靠的法律判断保证，正式使用须核对输出与适用法规。
- 支持 TXT、MD、CSV、可提取文字的 PDF、DOCX，最多 3 个文件，每个 15 MB。DOCX 提取正文段落和表格，不包含图片 OCR、批注、修订、页眉页脚或嵌入对象；PDF 遇到无文字页会提示处理，防止整页遗漏。即使存在文字层，图像里的内容也需人工确认。
- 原界面允许的图像、音视频、远程 URL、旧版 DOC 未在本项目加入解析能力。原 DSL 也未启用视觉或语音节点。此项目明确限制上传类型；需要这些能力时应单独扩展并测试。
- 原 Dify 自动生成回答后建议问题功能未复制；本界面保留四个开场任务入口。语音功能在原版中关闭。

## 命令行与验证

```powershell
.\.venv\Scripts\python.exe cli.py --check
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe cli.py --query "请检查这段宣传文案：……"
.\.venv\Scripts\python.exe cli.py --query "请审查合同" --file "合同.docx" --output "reports\合同审查.md"
.\.venv\Scripts\python.exe cli.py --mode faithful --query "请审查产品：……"
.\.venv\Scripts\python.exe cli.py --graph
```

自动测试使用明确标注的模拟模型与规则，验证路由、原始变量问题、修复后的正文/法规传递、无匹配分类、输入限制、DOCX 表格顺序、PDF 空页、密钥错误脱敏、Dify 响应映射、本地检索和界面提交。自动测试不验证真实模型的金融审查正确率。测试数据保留在 `.runtime/testdata/`，不执行批量删除。

## 参赛演示建议

1. 介绍原 Dify 工作流与本工程的节点映射，打开修正版图示。
2. 分别演示合同、产品、投资范围、营销文案四类材料，以及一般咨询。
3. 展示原文对应的风险项、法规参考片段和执行路径，下载审查报告。
4. 展示原版对照的合同接线问题，再展示修正后实际传入的材料与法规。
5. 对空材料、资料不足、文件解析失败进行演示，解释系统会明确反馈限制。

参赛前仍需：补齐原知识库；配置并验证真实模型；用相同输入与 Dify 逐项对比分类、证据命中和风险结论；根据具体赛题核对模型、联网、数据与提交格式要求。比赛规则尚未提供，本工程未声称已满足特定赛事资格。

## 工程结构

```text
app.py                         Streamlit 演示界面
cli.py                         命令行与配置检查
finance_assistant/config.py    运行配置与密钥读取
finance_assistant/workflow.py  DSL 映射、LangGraph、修复补丁
finance_assistant/providers.py 模型调用、本地/Dify 检索
finance_assistant/documents.py 文本、PDF、DOCX 解析
tests/test_workflow.py          自动验证
knowledge/                     用户提供的法规原文
docs/                          节点映射、流程图和验收记录
```

## 官方接口资料

- [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)
- [DeepSeek API](https://api-docs.deepseek.com/)
- [Dify 知识库检索 API](https://docs.dify.ai/en/api-reference/knowledge-bases/retrieve-chunks-from-a-knowledge-base-test-retrieval)
- [Dify DSL 导出说明](https://docs.dify.ai/en/cloud/use-dify/workspace/app-management)

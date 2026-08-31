# Spec: D1 RAG Agent Demo

状态：Approved for implementation，2026-08-31

## Objective

构建一个可在本地运行的 D1 学习项目，展示一个受控的单 Agent 技术资料问答闭环：

1. 启动时读取 5 篇 Markdown 文档并重新建立一次 RAG 索引快照；
2. 每个文档切成可检索 chunk，并保存标题、文档 ID、chunk ID、租户和权限元数据；
3. 用户通过 CLI 输入问题和身份；
4. Agent 只能调用一个只读的 `search_knowledge` Tool；
5. 查询阶段先做权限过滤，再进行向量检索和 top-k 筛选；
6. LLM 根据用户问题和检索证据生成带来源的结构化回答；
7. 无可用证据时明确拒答，不依赖模型的常识补全；
8. Harness 限制工具调用次数、校验工具参数、校验最终 JSON 和来源 ID，并记录一次 Run 的状态。

项目目标是帮助学习者理解 Agent 的控制循环、Tool、RAG、权限、状态、停止条件和输出校验，不追求复杂框架或多 Agent。

## Assumptions

1. 项目位于学习仓库的 `projects/rag-agent-demo/`。
2. 使用 Python 3.11+，第一版使用真实的 OpenAI Embeddings API 和 Qdrant 向量数据库；不要求在本机实际运行外部服务。
3. 核心代码定义 `EmbeddingProvider`、`VectorStore` 和 `ModelClient` 接口，供应商 SDK 只出现在适配器边界；测试使用 fake adapter。
4. 默认 Embedding 模型通过 `EMBEDDING_MODEL` 配置，示例默认 `text-embedding-3-small`；聊天模型通过 `MODEL_NAME` 配置，业务逻辑不写死模型名称。
5. 真实模型代码使用 OpenAI Responses API 的 Tool Calling 和 Structured Output；如果没有凭证，仍可通过 fake adapter 阅读和测试控制逻辑。
6. 权限以文档级为主：每篇文档在 manifest 中声明 `tenant_id` 和 `allowed_groups`，切块后复制到每个 chunk。查询时必须使用当前用户的租户和群组再次过滤。
7. 每次进程启动都重新摄取文档并执行一次索引快照写入；开发模式允许重建 collection。代码注释说明生产环境应使用 versioned collection + alias swap 或等价的原子切换。
8. 使用 CLI 作为最小用户界面；暂不实现浏览器前端，理由是 D1 先验证 Agent 核心闭环。
9. 只有一个只读 Tool，不实现写操作、人工审批、多 Agent、后台任务或网络检索。

## Tech Stack

- Python 3.11+
- `openai`：Embedding API、Responses API Tool Calling 和 Structured Output
- `qdrant-client`：向量 collection、payload、权限过滤、upsert 和 query_points
- `pydantic`：工具输入与最终输出 Schema 校验
- Python standard library：`dataclasses`、`json`、`pathlib`、`re`、`hashlib`、`logging`
- `unittest`：单元测试、集成测试和少量轨迹断言
- 测试用 fake model/embedding/vector store 替换外部服务，不把 fake 当作生产实现

## Project Structure

```text
projects/rag-agent-demo/
├── SPEC.md
├── README.md
├── pyproject.toml
├── data/
│   ├── manifest.json                 # 文档标题、租户和权限来源
│   └── documents/                    # 5 篇示例 Markdown 文档
├── rag_agent_demo/
│   ├── __init__.py
│   ├── cli.py                        # CLI 输入和用户可见输出
│   ├── config.py                     # top-k、阈值、步数和重试配置
│   ├── contracts.py                  # Tool、RunState、最终输出的数据契约
│   ├── ingest.py                     # Markdown 读取、切块和元数据合并
│   ├── embeddings.py                 # OpenAI Embedding adapter 与批处理
│   ├── vector_store.py               # Qdrant collection、payload filter 和 query_points
│   ├── tools.py                      # search_knowledge Tool 实现
│   ├── model.py                      # OpenAI Responses adapter 与测试替身
│   ├── output_validation.py          # JSON/Schema/source 引用校验
│   ├── agent.py                      # Harness 与受控 Agent Loop
│   └── tracing.py                    # Run/Tool/Model 事件记录
├── evals/
│   ├── cases.json                    # 有答案、无答案、权限边界用例
│   └── run_evals.py                  # 离线评测入口
└── tests/
    ├── test_ingest.py
    ├── test_embeddings.py
    ├── test_permissions.py
    ├── test_retrieval.py             # fake embedding + fake vector store 的检索规则
    ├── test_output_validation.py
    └── test_agent_loop.py
```

## Data and Permission Contract

权限定义在 `data/manifest.json`，不放进自然语言正文，避免把访问控制当成 Prompt 规则。例如：

```json
[
  {
    "document_id": "agent-basics",
    "path": "documents/agent-basics.md",
    "title": "Agent 基础",
    "tenant_id": "demo",
    "allowed_groups": ["engineering"]
  }
]
```

摄取后每个 chunk 至少包含：

```json
{
  "chunk_id": "agent-basics-003",
  "document_id": "agent-basics",
  "title": "Agent 基础",
  "source_path": "documents/agent-basics.md",
  "tenant_id": "demo",
  "allowed_groups": ["engineering"],
  "heading": "Agent Loop",
  "text": "..."
}
```

检索必须先应用：

```text
chunk.tenant_id == current_user.tenant_id
and intersection(chunk.allowed_groups, current_user.groups) is not empty
```

未授权文档对当前用户表现为“不存在”，不得进入候选集、top-k、模型上下文或 Trace 正文。

## Control Flow

### Startup

```text
读取 manifest
→ 校验每个 path 在 data/documents 目录内
→ 读取 Markdown
→ 按标题/段落切 chunk
→ 复制权限元数据
→ 批量调用 Embedding API
→ 创建或重建 Qdrant collection
→ upsert 向量、正文和权限 payload
```

### One Run

```text
CLI 接收 question + user identity
→ 创建 RunState
→ 第一次调用 ModelClient，并暴露 search_knowledge Tool
→ 要求模型先调用 Tool
→ Harness 校验 tool name、参数和调用次数
→ Tool 将租户/群组权限编译为 Qdrant payload filter
→ Qdrant 在检索阶段过滤，再返回 top-k matches
→ 若没有可用 matches，程序进入 no_evidence 并直接返回拒答
→ 否则将 question + tool result + 输出 Schema 交给 LLM
→ LLM 输出 answerable/answer/sources
→ Harness 解析 JSON、校验 Schema 和 source IDs
→ 返回 CLI
```

如果第一次模型响应直接是 text 而没有调用 Tool，Harness 只允许一次修复：追加“本问题必须先检索”的控制消息并重试。第二次仍不调用 Tool，则以 `policy_violation` 结束，不把未经检索的文本当作答案。

## Contracts

### `search_knowledge` Tool

输入：

```json
{
  "query": "什么是 Agent Loop？",
  "top_k": 3
}
```

输出：

```json
{
  "matches": [
    {
      "chunk_id": "agent-basics-003",
      "title": "Agent 基础",
      "text": "...",
      "score": 0.82
    }
  ],
  "retrieval_status": "matched"
}
```

没有通过相关性规则的候选时：

```json
{
  "matches": [],
  "retrieval_status": "no_relevant_match"
}
```

`retrieval_status` 表示检索规则的结果，不保证最终一定能回答问题。

### Final Output

LLM 的最终输出要求为固定字段的 JSON：

```json
{
  "answerable": true,
  "answer": "...",
  "sources": [
    {"chunk_id": "agent-basics-003", "title": "Agent 基础"}
  ]
}
```

当证据不足时：

```json
{
  "answerable": false,
  "answer": "现有资料中没有找到足够依据。",
  "sources": []
}
```

输出校验必须确认：

- JSON 可解析；
- 必填字段和字段类型正确；
- `answerable` 是布尔值；
- 每个 `source.chunk_id` 都来自本次检索结果；
- `sources` 不得引用未授权文档；
- 没有检索证据时不能生成具体事实答案。

## State and Termination

`RunState` 至少记录：

- `run_id`、用户身份和问题；
- 当前阶段：`created`、`awaiting_tool`、`retrieved`、`generating`、`completed`、`no_evidence`、`failed`；
- `tool_calls` 和 `retrieval_called`；
- 检索到的 chunk ID；
- 最终输出或错误类别；
- 模型/工具耗时。

正常停止条件：

- 收到合法的最终结构化输出；
- 无可用证据并返回固定拒答。

保护性停止条件：

- RAG Tool 调用次数超过 1；
- 首次未调用 Tool 且一次修复仍失败；
- 最终 JSON 无法解析或校验失败；
- 模型/工具异常或超时；
- 达到最大轮次。

## Failure Policy

- `no_relevant_match`：正常业务结果，不重试，用户看到“当前资料中没有找到足够依据”。
- 临时模型/HTTP 失败：最多重试一次；失败后返回“回答服务暂时不可用”。
- Tool 参数错误：严格校验后立即作为 `invalid_tool_arguments` 失败，不把协议错误伪装成检索服务故障；最终 JSON 格式或来源校验错误时最多修复一次，仍失败则返回“暂时无法生成有效回答”。
- 权限不足：不把文档是否存在暴露给用户，返回“当前资料中没有可用依据”。
- 索引损坏、manifest 错误、路径越界：启动失败并给出管理员可诊断错误；不在请求阶段反复重试。

## Evaluation and Testing Strategy

至少包含以下离线评测：

1. 能回答且引用正确；
2. 无相关文档时拒答；
3. top-k 中有相似但不支持答案的内容时拒答；
4. engineering 用户不能看到 support-only 文档；
5. 不同 tenant 的文档不能互相检索；
6. 第一次模型直接返回 text 时触发一次修复；
7. 第二次仍不调用 Tool 时停止；
8. 最终 JSON 有未知 `source_id` 时拒绝；
9. RAG Tool 最多调用一次；
10. 每次启动重新建立索引；没有外部服务时可通过 fake adapter 运行控制逻辑测试。

确定性测试优先检查权限、调用次数、状态、Schema 和引用；真实 Embedding/LLM 的集成边界通过 fake adapter 做契约测试，语义质量使用人工标注的小样本检查，不把 LLM judge 当作唯一真值。

## Observability

每次 Run 记录带 UTC 时间戳的结构化事件：

- `run_started`；
- `model_response`（不默认记录完整敏感正文）；
- `tool_called`；
- `retrieval_completed`（候选数量、状态和 chunk ID）；
- `output_validated`；
- `run_completed` 或 `run_failed`。

CLI 默认展示最终状态和来源；详细 Trace 通过 `--trace` 输出，便于学习失败定位。

## Commands

```text
python -m unittest discover -s tests -v
python -m rag_agent_demo.cli --question "什么是 Agent Loop？" --tenant demo --groups engineering
python -m evals.run_evals
```

真实模型配置为可选项，使用环境变量，不把密钥写入文件：

```text
OPENAI_BASE_URL
OPENAI_API_KEY
MODEL_NAME
EMBEDDING_MODEL
```

## Code Style

- 使用 dataclass 表达状态和跨模块契约；
- 工具函数保持单一职责；
- 业务策略使用显式命名的配置，不把阈值散落在代码中；
- 对外部输入、Tool 参数和 LLM 最终输出都进行校验；
- 注释解释“为什么需要边界”，不重复“这行代码做了什么”。

示例风格：

```python
def filter_authorized(chunks: list[Chunk], user: User) -> list[Chunk]:
    """Apply authorization before ranking so unauthorized data cannot affect top-k."""
    return [
        chunk
        for chunk in chunks
        if chunk.tenant_id == user.tenant_id
        and set(chunk.allowed_groups) & set(user.groups)
    ]
```

## Boundaries

### Always

- 权限过滤先于排序和上下文装配；
- 默认禁止网络和写入工具；
- 限制检索次数、模型修复次数和最大轮次；
- 不把 LLM 输出直接当作已验证事实；
- 运行测试和离线评测；
- 注释关键的权限、无答案和终止边界。

### Ask First

- 引入第三方依赖或下载模型；
- 选择具体模型供应商和 SDK；
- 增加浏览器前端、持久化向量数据库或真实用户认证；
- 修改当前学习仓库之外的文件。

### Never

- 把 API Key、真实用户数据或敏感文档提交到仓库；
- 只在 Prompt 中实现授权；
- 先检索所有文档再做事后权限过滤；
- 用空 top-k 或模型相似度分数直接证明答案正确；
- 允许无限重试、无限 Tool Loop 或未经校验的来源引用。

## Success Criteria

实现完成后，学习者可以：

1. 一条命令启动并重新摄取 5 篇文档；
2. 用不同群组用户复现允许和拒绝的检索结果；
3. 观察一次 `tool_call → tool_result → final JSON` 的完整 Trace；
4. 解释 `retrieval_status` 与 `answerable` 的区别；
5. 复现无证据、越权、格式错误、重复 Tool Call 和模型直接返回 text 的分支；
6. 所有测试和 10 条离线评测通过；
7. 不配置 API Key 时仍能运行 fake adapter 的控制逻辑测试和离线评测；
8. README 能说明哪些能力已实现、哪些是有意省略以及为什么。

## Open Questions

1. 是否要在后续版本增加第二个 Embedding 供应商，当前第一版固定 OpenAI + Qdrant 作为真实实现；
2. 是否需要把 CLI 扩展为浏览器页面；这会扩大 D1 项目的 UI 范围；
3. 生产部署时使用 Qdrant Cloud、托管 Qdrant 还是自建 Qdrant，由部署环境决定。

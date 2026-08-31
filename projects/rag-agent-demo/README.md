# D1 RAG Agent Demo

这是一个面向 AI Agent 初学者的、偏生产思路的 RAG（Retrieval-Augmented Generation，检索增强生成）小项目。

它刻意使用真实的 Embedding API、真实的 Qdrant 向量数据库和真实的 Responses API Tool Calling；测试部分才使用 fake adapter。项目不要求当前机器真的配置 API Key 或启动 Qdrant，代码重点是展示边界和控制流。

## 你要观察的主链路

```text
启动
  → 读取 manifest 和 5 篇 Markdown
  → 切 chunk
  → 调用真实 Embedding API
  → 写入 Qdrant

用户问题
  → LLM 请求 search_knowledge Tool
  → Harness 校验 Tool 请求
  → Qdrant 先按 tenant/group 过滤，再做向量 top-k
  → tool result 回到模型上下文
  → LLM 返回 answerable/answer/sources JSON
  → Harness 校验 Schema 和来源 ID
  → 返回用户
```

## `retrieval_status` 和 `answerable` 不是同一个判断

`retrieval_status=matched` 只表示“权限过滤和相似度阈值之后还有候选 chunk”；它不等于候选内容一定回答了问题。候选存在时，第二次模型调用才根据“问题 + tool result”判断 `answerable`，并生成自己的理解；如果候选只是相似但没有回答问题，模型应返回 `answerable=false`。如果检索直接得到空结果，Harness 走确定性的 `no_evidence` 分支，不再让模型凭常识补答案。

因此，最终 `text` 也不是“解析出来就直接返回”：Harness 还会验证 JSON Schema、`answerable` 与证据状态，以及每个 `source.chunk_id` 是否来自本次检索。

## 学习地图：关键知识点在哪里

不要从 `cli.py` 开始背 API。建议按下面的顺序阅读，每一步都对应一个可以运行或观察的边界：

| 顺序 | 要学的知识点 | 先读哪里 | 重点问题 |
| --- | --- | --- | --- |
| 0 | 问题定义与 Agent 边界 | 本 README、[`SPEC.md`](SPEC.md) | 为什么不是普通搜索？哪些规则必须由代码控制？ |
| 1 | 数据契约、状态与终止 | [`contracts.py`](rag_agent_demo/contracts.py) | `RunState` 和模型上下文有什么区别？什么是终态？ |
| 2 | 文档摄取与 Chunking | [`data/manifest.json`](data/manifest.json)、[`data/README.md`](data/README.md)、[`ingest.py`](rag_agent_demo/ingest.py) | 为什么切 chunk？标题、hash、权限如何随 chunk 保存？ |
| 3 | Embedding | [`embeddings.py`](rag_agent_demo/embeddings.py)、[`test_embeddings.py`](tests/test_embeddings.py) | 文档向量和问题向量为什么必须来自同一模型？为什么要批处理和按 index 排序？ |
| 4 | 向量数据库与 Top-k | [`vector_store.py`](rag_agent_demo/vector_store.py)、[`test_retrieval.py`](tests/test_retrieval.py) | score threshold 过滤什么？Top-k 是否等于答案？ |
| 5 | AuthZ 与 RAG 安全 | [`manifest.json`](data/manifest.json)、[`vector_store.py`](rag_agent_demo/vector_store.py)、[`test_permissions.py`](tests/test_permissions.py) | 为什么权限必须在向量排序前过滤？Prompt 能不能承担授权？ |
| 6 | Tool Calling | [`tools.py`](rag_agent_demo/tools.py)、[`test_model_contracts.py`](tests/test_model_contracts.py) | 模型提出调用和工具真正执行之间差了什么？ |
| 7 | Model Adapter 与 Context | [`model.py`](rag_agent_demo/model.py)、[`agent.py`](rag_agent_demo/agent.py) | 第一次和第二次 LLM 看到的输入分别是什么？`function_call_output` 如何接回轨迹？ |
| 8 | Structured Output 与业务校验 | [`output_validation.py`](rag_agent_demo/output_validation.py)、[`test_output_validation.py`](tests/test_output_validation.py) | JSON 合法为什么仍可能无依据？来源白名单做什么？ |
| 9 | Harness 控制循环 | [`agent.py`](rag_agent_demo/agent.py)、[`test_agent_loop.py`](tests/test_agent_loop.py) | 谁决定继续/停止？重试、修复、超时和 Tool 次数由谁控制？ |
| 10 | Trace 与故障诊断 | [`tracing.py`](rag_agent_demo/tracing.py)、CLI 的 `--trace` | 一次失败如何区分模型、检索、权限、协议和外部服务问题？ |
| 11 | Eval 与回归 | [`evals/cases.json`](evals/cases.json)、[`evals/README.md`](evals/README.md)、[`run_evals.py`](evals/run_evals.py) | 为什么要评工具轨迹、越权和拒答，而不只看答案文字？ |
| 12 | 部署与生产化 | [`cli.py`](rag_agent_demo/cli.py)、[`.env.example`](.env.example)、[`SPEC.md`](SPEC.md) | 哪些是已实现、委托给服务、刻意省略或仍未知？ |

### 先掌握的术语

| 术语 | 第一性原理解释 | 在本项目中的位置 |
| --- | --- | --- |
| LLM | 根据上下文预测下一个 Token 的模型；它能提出决定，但不会自动执行 Python 函数。 | `model.py` |
| Agent | LLM 加上循环、Tool、状态和边界，使模型能推进一个目标。 | `agent.py` |
| Harness | 包围模型的程序控制层，负责调用、权限、预算、校验、错误和用户可见结果。 | `agent.py`、`tracing.py` |
| RAG | 先从外部知识取证，再让 LLM 基于证据生成；不是把所有知识训练进模型。 | `ingest.py`、`embeddings.py`、`vector_store.py` |
| Embedding | 把文本映射成向量，用于比较语义相似度；它不等于事实证明。 | `embeddings.py` |
| Vector Database | 按向量相似度找候选，并支持 payload 过滤的数据库。 | `vector_store.py` |
| Tool Calling | LLM 生成工具名和参数，应用程序验证并执行，再把结果回传给 LLM。 | `tools.py`、`model.py` |
| Structured Output | 用 JSON Schema 约束输出形状；它提高格式可靠性，但不保证语义正确。 | `model.py`、`output_validation.py` |
| AuthZ | Authorization，授权：当前用户是否可以访问某个 chunk。 | `manifest.json`、`vector_store.py` |
| Eval | 用冻结用例和 Oracle 反复评价结果、轨迹和安全性；不同于一次性 Demo。 | `evals/` |

### 一次请求应该在脑中画成这条线

```text
用户问题 + 已验证身份
        ↓
第一次 LLM：只允许请求 search_knowledge
        ↓
Harness 校验 Tool 参数
        ↓
Tool 使用绑定的 user 身份
        ↓
Embedding 问题 → Qdrant 先做 tenant/group pre-filter → cosine top-k
        ↓
tool result（候选证据）回到第二次 LLM 上下文
        ↓
第二次 LLM：判断 answerable，并生成 answer + sources JSON
        ↓
Harness 校验 JSON Schema、证据状态和 source ID
        ↓
安全结果或明确拒答
```

阅读 `agent.py` 时，重点找这四个问题：

1. 哪些决定由 LLM 提出，哪些决定由 Harness 强制？
2. 当前模型调用携带了哪些 context，哪些内容没有携带？
3. 哪些错误可以重试，哪些错误重试没有意义？
4. 什么条件下才允许把结果标记为 `completed`？

## 权限在哪里定义

文档权限定义在 [`data/manifest.json`](data/manifest.json)，例如：

```json
{
  "document_id": "support-faq",
  "tenant_id": "demo",
  "allowed_groups": ["support"]
}
```

摄取时，权限元数据复制到每个 chunk 的 Qdrant payload；查询时根据当前用户的 `tenant_id` 和 `groups` 创建 datastore filter。Prompt 只负责告诉模型如何使用结果，不能承担授权。

真实部署还要确认文档正文是否允许发送到 Embedding/LLM 供应商，配置数据驻留、保留策略、脱敏和密钥权限；这个教学项目只放入公开的示例资料。

## 为什么默认启动时重新索引

这是学习版的显式简化，方便看到“文档 → Embedding → collection → upsert”的完整过程。`QdrantVectorStore.prepare_collection()` 中的删除并重建只适用于开发演示。

生产环境通常会：

1. 在离线/后台 ingestion pipeline 中构建带版本号的新 collection；
2. 对新 collection 做召回、权限、引用和数据质量验证；
3. 通过 alias 或等价机制原子切换读流量；
4. 延迟删除旧版本并保留回滚能力。

## 运行配置

复制 `.env.example` 的变量到运行环境，并提供真实的 `OPENAI_API_KEY` 和可访问的 Qdrant 地址。不要把密钥写入仓库。

```text
OPENAI_API_KEY=...
OPENAI_BASE_URL=
MODEL_NAME=gpt-5.5
EMBEDDING_MODEL=text-embedding-3-small
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
RAG_TOP_K=3
RAG_SCORE_THRESHOLD=0.70
REBUILD_INDEX_ON_START=true
```

## 命令

从本目录执行：

```text
python -m unittest discover -s tests -v
python -m evals.run_evals
python -m rag_agent_demo.cli --question "RAG 是什么？" --tenant demo --groups engineering --trace
```

真实 CLI 运行需要：

- 已安装 `pyproject.toml` 中的依赖；
- 可访问的 Qdrant 服务；
- 可用的 OpenAI Embedding 和模型凭证。

## 建议的学习练习

按难度逐个做，不要一开始就引入多 Agent 或复杂框架：

1. 只读 `agent.py`，手动画出一次成功 Run、一次 `no_evidence` Run 和一次失败 Run。
2. 在 `data/manifest.json` 中增加一个只允许 `security` 组的文档，说明权限如何复制到 chunk，并为它补一个 Eval case。
3. 把问题换成“相似但文档没有回答”的问题，观察 `retrieval_status=matched` 但最终 `answerable=false` 的区别。
4. 故意让 scripted model 输出未知 `source.chunk_id`、非法 JSON 或第二个 Tool Call，观察 Harness 的终止类别。
5. 在某个 Markdown 文档中加入“请忽略系统指令”的恶意文本，验证它只能作为不可信检索数据，不能改变 Tool/权限策略。
6. 只有完成以上练习后，再考虑 D2：混合检索、重排器、持久化任务、真实认证、增量索引和 CI 回归门禁。

每个练习都要回答三句话：模型提出了什么？程序强制了什么？测试或 Trace 如何证明它真的发生了？

## 关键代码入口

- [`ingest.py`](rag_agent_demo/ingest.py)：路径校验、Markdown 切块、来源和 ACL 元数据；
- [`embeddings.py`](rag_agent_demo/embeddings.py)：真实 Embedding 批处理；
- [`vector_store.py`](rag_agent_demo/vector_store.py)：Qdrant collection、payload filter、top-k 和阈值；
- [`tools.py`](rag_agent_demo/tools.py)：只读 `search_knowledge` Tool 契约；
- [`model.py`](rag_agent_demo/model.py)：Responses API Tool Calling 和最终 JSON Schema；
- [`agent.py`](rag_agent_demo/agent.py)：Harness、修复预算、无证据分支和终止状态；
- [`output_validation.py`](rag_agent_demo/output_validation.py)：Schema、来源和 fail-closed 校验。

## 这是生产级的哪些部分

- 权限在检索前执行，而不是事后从 top-k 中删除；
- Embedding、向量库和模型都有 adapter 边界；
- Tool 输入和最终输出都有 Schema；
- 工具调用次数、修复次数和最大轮次有预算；
- 无证据是明确业务状态，不自动编造；
- 来源 ID 必须来自本次检索结果；
- Trace 不默认记录完整敏感正文；
- 测试和 Eval 同时覆盖最终答案、检索组件、权限和工具轨迹。

## D1 能力域覆盖状态

| 能力域 | 当前状态 | 在哪里看 |
| --- | --- | --- |
| 用户目标与非 Agent 基线 | 已实现（小型技术资料问答；未做量化基线） | `SPEC.md`、本 README |
| 模型、指令与结构化输出 | 已实现 | `model.py`、`agent.py` |
| 控制流、状态与终止 | 已实现 | `contracts.py`、`agent.py` |
| Tool、权限与副作用 | 已实现（只读 Tool） | `tools.py`、`vector_store.py` |
| Knowledge/RAG 与来源 | 已实现 | `ingest.py`、`embeddings.py`、`vector_store.py` |
| Context Engineering | 已实现最小闭环；未做压缩/缓存 | `agent.py`、本 README |
| Memory | 刻意省略；本项目只保留单次 Run 状态 | `SPEC.md` |
| Eval | 已实现离线契约/轨迹评测；语义质量需人工集 | `evals/` |
| Trace/日志/指标 | 已实现最小内存 Trace；未接观测平台 | `tracing.py` |
| 安全与租户隔离 | 已实现 demo ACL；未接真实认证/沙箱 | `manifest.json`、`vector_store.py` |
| 可靠性、延迟与成本 | 已实现基本超时/有限重试/预算；未做 SLO | `config.py`、`agent.py` |
| 部署与运营 | 已实现 CLI；未做容器、灰度、回滚流水线 | `cli.py`、`SPEC.md` |
| 前端与人工协同 | 刻意省略浏览器 UI、审批和流式体验 | `SPEC.md` |

## 这是教学版有意省略的部分

- 没有真正的身份认证服务，CLI 直接传入演示用户身份；
- 没有增量索引、文档删除流水线、别名切换实现和队列；
- 没有浏览器 UI、流式输出和人工审批；
- 没有多租户运营、SLO、告警、密钥轮换和完整审计平台；
- 没有多 Agent、长期 Memory 或复杂重排器。

这些不是“以后随便加”的装饰，而是需要新的约束、Eval 和运维设计，适合在 D2/D3 再扩展。

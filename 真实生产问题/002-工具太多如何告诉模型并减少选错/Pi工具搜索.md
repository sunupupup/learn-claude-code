# Pi：搜索由谁提供、动态工具如何进入模型请求

**结论：Pi 0.87.1 固定核心中，本次未找到默认的工具搜索器或工具检索索引。它已经实现动态启用工具及多供应商的工具定义加载适配；“支持加载”不能当成“默认自动检索”。**

- 核验日期：2026-10-16；官方仓库 [earendil-works/pi](https://github.com/earendil-works/pi)，Commit `d6af72e1857cfb10b41d8ff8e69f0d72b4cf6d31`，`@earendil-works/pi-coding-agent` **0.87.1**。
- 🟢 已阅读工具注册／启用、Agent loop、Transcript（会话记录）及 Anthropic/OpenAI 适配代码；未运行工具扩展或模型请求。
- 检索范围：`packages/coding-agent/src`、`packages/agent/src`、官方扩展示例及 Git 跟踪路径；未找到核心 MCP 搜索工具。第三方包、其他分支和后续版本不在此结论范围内。

## 1. search tool 内部实现：默认没有，扩展负责

Pi 的 `_toolRegistry: Map<string, AgentTool>` 是**工具注册表**，不是向量库或搜索引擎。`setActiveToolsByName` 根据名字从 Map 取工具，把结果写入 `agent.state.tools`，并重建系统提示。

```text
扩展可实现 search_tools(query)                 ← 检索算法由扩展决定
→ 扩展选择工具名                            ← Pi 没有默认语义排名
→ setActiveTools([...原活动工具名, ...命中名])
→ agent.state.tools 更新
→ 下一轮 loop 把工具变化转换成供应商请求
```

这是**可实现的扩展链路示意**，不是已存在、已验证的内置 `search_tools`。`setActiveTools` 是替换活动集合，扩展若要保留搜索入口和现有工具，应自行合并；不能只传命中工具后丢掉原集合。

- [setActiveToolsByName:1282](https://github.com/earendil-works/pi/blob/d6af72e1857cfb10b41d8ff8e69f0d72b4cf6d31/packages/coding-agent/src/core/agent-session.ts#L1282)：只接受已经注册的工具，未知名字被忽略。
- [扩展接口接到会话：3084](https://github.com/earendil-works/pi/blob/d6af72e1857cfb10b41d8ff8e69f0d72b4cf6d31/packages/coding-agent/src/core/agent-session.ts#L3084)。
- [官方 dynamic-tools 示例](https://github.com/earendil-works/pi/blob/d6af72e1857cfb10b41d8ff8e69f0d72b4cf6d31/packages/coding-agent/examples/extensions/dynamic-tools.ts)：演示运行时 `registerTool`，**没有检索算法**。

## 2. 内部检索与“向量入库”参数

| 关注项 | 该固定核心的实际情况 |
|---|---|
| 默认搜索函数／返回 key 格式 | 未找到；不得编造内置 `search_tools` 返回协议 |
| BM25／向量检索 | 未找到默认实现；注册表 Map 的名字查找不属于相关性检索 |
| 入库文本、Embedding 模型、维度 | 核心没有这套工具搜索配置 |
| top-k、相似度阈值、HNSW 参数 | 核心没有这套工具搜索配置 |
| 实际已有能力 | 按名查工具、切换活动集合、登记运行中的工具变更、适配供应商加载协议 |

如果扩展使用向量检索，入库与查询必须由该扩展实现并核验，不能从 `pi.registerTool` 或 `setActiveTools` 推导它自动具备向量搜索。

## 3. 新选中的工具怎样进入后续 LLM call

### 先形成与供应商无关的工具变更记录

[agent-loop.ts:332](https://github.com/earendil-works/pi/blob/d6af72e1857cfb10b41d8ff8e69f0d72b4cf6d31/packages/agent/src/agent-loop.ts#L332) 的 `declareToolChanges` 在请求前，对比记录里已经声明的工具与当前可执行集合，形成下面的内部消息（教学示意，省略时间和完整参数定义）：

```text
{
  role: "system",
  content: "",
  toolsAdded: [{name: "get_order", description: "…", parameters: {…}}],
  toolsRemoved: []
}
```

`toolsAdded` 是 Pi 内部字段，**不是可原样发送给所有 LLM 的通用 API 格式**。后续由 Provider adapter（供应商协议转换层）决定怎样传。

### 按供应商能力走不同路径

| 路径 | 实际发送的定义形式 | 回退条件 |
|---|---|---|
| Anthropic 支持会话中工具变更 | 顶层声明初始工具与后续工具；后续项标 `defer_loading: true`；消息内发送 `tool_addition → tool_reference(name)` | 不支持、没有初始工具、同名工具定义被改写时，发送当前完整顶层 `tools` |
| OpenAI Responses 支持 `additional_tools` | 在 `input` 中追加 `{type:"additional_tools", role:"developer", tools:[完整声明]}`，顶层保留初始集合 | 删除或重定义工具时，纯追加路径回退为当前完整集合 |
| 只支持 Responses Tool Search 加载协议 | 在 `input` 中生成配对的 `tool_search_call` 和 `tool_search_output`，后者携带完整声明 | 不支持加载能力时回退顶层集合 |
| 不支持相应追加能力的接口 | 当前完整可用集合转换成顶层 `tools` | 工具集合变化可能影响缓存，不能声称保留前缀 |

**关键区别：这里自动生成 `tool_search_call` 是把已经选好的定义适配到供应商协议，不是 Pi 在此处又做了一次关键词或向量检索。**

源码连接点：

- [通用工具差异计算：transcript.ts:150](https://github.com/earendil-works/pi/blob/d6af72e1857cfb10b41d8ff8e69f0d72b4cf6d31/packages/ai/src/utils/transcript.ts#L150)；[决定保留初始工具还是发送当前集合：226](https://github.com/earendil-works/pi/blob/d6af72e1857cfb10b41d8ff8e69f0d72b4cf6d31/packages/ai/src/utils/transcript.ts#L226)。
- Anthropic：[能力检查：1056](https://github.com/earendil-works/pi/blob/d6af72e1857cfb10b41d8ff8e69f0d72b4cf6d31/packages/ai/src/api/anthropic-messages.ts#L1056)、[顶层延迟声明：1123](https://github.com/earendil-works/pi/blob/d6af72e1857cfb10b41d8ff8e69f0d72b4cf6d31/packages/ai/src/api/anthropic-messages.ts#L1123)、[消息中的引用块：1264](https://github.com/earendil-works/pi/blob/d6af72e1857cfb10b41d8ff8e69f0d72b4cf6d31/packages/ai/src/api/anthropic-messages.ts#L1264)。此版本用 `mid-conversation-tool-changes-2026-07-01`，不是前文新 Beta 的完整 `tool_definition` 方式。
- Responses：[追加定义和 Tool Search 回退：openai-responses-shared.ts:184](https://github.com/earendil-works/pi/blob/d6af72e1857cfb10b41d8ff8e69f0d72b4cf6d31/packages/ai/src/api/openai-responses-shared.ts#L184)；[构造实际请求：openai-responses.ts:294](https://github.com/earendil-works/pi/blob/d6af72e1857cfb10b41d8ff8e69f0d72b4cf6d31/packages/ai/src/api/openai-responses.ts#L294)。
- Chat Completions：[能力与集合选择：openai-completions.ts:808](https://github.com/earendil-works/pi/blob/d6af72e1857cfb10b41d8ff8e69f0d72b4cf6d31/packages/ai/src/api/openai-completions.ts#L808)、[顶层 tools：851](https://github.com/earendil-works/pi/blob/d6af72e1857cfb10b41d8ff8e69f0d72b4cf6d31/packages/ai/src/api/openai-completions.ts#L851)。

## 4. 你关心的向量配置：与这三个产品的已核验路径分开

三份笔记没有核到默认语义向量工具检索；不能为产品填写不存在的向量库参数。若之后研究使用向量检索的扩展，必须查这些具体项：

| 阶段 | 要核验的参数及数据 |
|---|---|
| 入库文本 | 名称、描述、参数说明中哪些参与 embedding；一个工具一条还是拆块 |
| 向量生成 | Embedding 模型与版本、维度、是否归一化；查询与入库使用兼容模型 |
| 关联与过滤 | 稳定 tool ID、工具 Schema 版本、所属服务、租户／权限元数据与更新删除策略 |
| 索引 | 内存精确扫描，还是 HNSW / IVF；后两者才有 `M`、`efConstruction`、`nlist` 等对应设置 |
| 查询 | top-k、cosine / dot / L2、阈值、权限过滤；HNSW 的 `efSearch`、IVF 的 `nprobe` 仅在对应索引中适用 |
| 后处理 | 是否 rerank（对候选二次排序）、去重、零匹配回退，以及加载数量预算 |

这些是**后续核验清单，不是 Pi 默认配置，也不是所有向量库统一支持的字段**。之前讨论的 [langgraph-bigtool 示例](https://github.com/langchain-ai/langgraph-bigtool/blob/081f74869e5e12ff45a867335f9443571234c8ab/README.md#L64-L88) 才明确配置了 `text-embedding-3-small`、1536 维、`fields=["description"]` 和 `InMemoryStore`；不要把该示例配置移植成 CC / Codex / Pi 的事实。


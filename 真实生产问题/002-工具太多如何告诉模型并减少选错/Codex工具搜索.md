# Codex：BM25 建索引、检索与正式工具加载

**结论：固定版本 Codex 使用本地 BM25 词法检索，不调用语义 Embedding 模型、不建向量数据库。搜索返回完整工具声明，通过 Responses API 的 `tool_search_output` 输入项进入后续模型调用。**

- 核验日期：2026-10-16；官方仓库 [openai/codex](https://github.com/openai/codex)，Commit `e72da2b53805894878023d01949a25a082e0a5cb`。
- 🟢 固定源码与锁定依赖 `bm25 2.3.2` 已阅读；未运行 Codex、MCP 或模型请求。结论限该版本及工具搜索启用路径，不代表桌面版全部内部实现。
- 启用判断：[spec_plan.rs:653](https://github.com/openai/codex/blob/e72da2b53805894878023d01949a25a082e0a5cb/codex-rs/core/src/tools/spec_plan.rs#L653) 要求模型 `supports_search_tool` 且 Provider 支持工具命名空间；不是所有模型统一启用。

## 1. search tool 内部做什么

入口：[ToolSearchHandler](https://github.com/openai/codex/blob/e72da2b53805894878023d01949a25a082e0a5cb/codex-rs/core/src/tools/handlers/tool_search.rs#L30)。

```json
{"query":"slack send message","limit":8}
```

1. `ToolSearchHandlerCache.get_or_build` 从工具注册表取得 **Deferred（延迟暴露）** 工具的 `ToolSearchInfo`。
2. 每条信息保存检索文本 `search_text` 和完整工具声明的引用，两者通过数组下标 ID 关联。
3. 取得或建立内存 BM25 搜索器；查询返回文档 ID 与分数。
4. 按 ID 找回工具声明，规范化成可加载的命名空间，合并同命名空间结果，返回 `ToolSearchOutput`。

不是模型从搜索结果里获得执行函数；真实执行入口仍在 Harness 注册表。

## 2. 关键检索：怎么“入库”、怎么查、哪些参数

### 建索引：一个搜索条目是一篇文档

[构建过程：tool_search.rs:143](https://github.com/openai/codex/blob/e72da2b53805894878023d01949a25a082e0a5cb/codex-rs/core/src/tools/handlers/tool_search.rs#L143)：将每条 `search_text` 建成 `Document(id, text)`，调用 `SearchEngineBuilder.with_documents(Language::English, documents).build()`。

**这里的“入库”是创建内存全文索引，没有数据库写入。** 工具来源与检索元数据不变时复用搜索器；来源、动态定义或来源展示配置变化时重建。

原始源码短摘录，仅增加中文注释；上游将每条检索文本组成 `documents`：

```rust
// 建立本地 BM25 索引；此处没有调用神经网络 Embedding 服务。
let search_engine =
    SearchEngineBuilder::<usize>::with_documents(Language::English, documents).build();
```

检索文本并非只有 `description`：

| 工具来源 | 实际加入检索文本的内容 |
|---|---|
| 普通函数／动态工具 | 名称、下划线转空格的名称、描述、参数名及参数描述，递归处理 properties / items / anyOf；命名空间工具还含命名空间信息 |
| MCP 工具 | 规范调用名、可调用名称、原始名、服务名、title、描述、连接器名、命名空间描述、插件展示名、**顶层参数名** |

来源：[默认文本拼装](https://github.com/openai/codex/blob/e72da2b53805894878023d01949a25a082e0a5cb/codex-rs/tools/src/tool_search.rs#L112)、[MCP 专用拼装](https://github.com/openai/codex/blob/e72da2b53805894878023d01949a25a082e0a5cb/codex-rs/core/src/tools/handlers/mcp.rs#L539)。不能把普通函数的参数描述递归规则套到 MCP 专用路径。

### 底层实际算法

已下载并核对 `Cargo.lock` 锁定的 **bm25 2.3.2**，源码放在本仓库外。不是只读到 `.search()` 就停止。

```text
建索引：文本规范化 → 转小写 → Unicode 词边界切词
→ 移除英文停用词 → 英文词干提取
→ 统计词频与平均文档长度 → 建立“词 → 文档 ID 集合”的倒排索引

查询：同样切词 → 从倒排索引取出包含查询词的候选（并集）
→ 每篇文档按 BM25 打分 → 降序排序 → 取 limit 个
```

**BM25 的作用：** 罕见匹配词贡献更大；同一个词重复出现的增益逐渐饱和；按文档长度校正分数。此库的打分是 `Σ IDF(查询词) × 文档内该词的归一化词频权重`，没有进行余弦相似度计算。

| 参数／设置 | 真实值与来源 | 含义 |
|---|---|---|
| 分词语言 | Codex 显式 `English` | 使用英文停用词和词干规则，不是 LLM tokenizer |
| normalization / stemming / stopwords | 依赖默认均为 `true` | 规范化、词干化、去停用词 |
| `k1` | 依赖默认 **1.2**；Codex 未覆盖 | 控制词频饱和速度 |
| `b` | 依赖默认 **0.75**；Codex 未覆盖 | 控制文档长度校正程度 |
| `avgdl` | 建索引时按全部文档的分词长度求平均 | 不是用户手填 |
| `query` | 模型生成，trim 后不能空 | 关键词检索，无专用 `select:` 或 `+必含词` 语法 |
| `limit` | 默认 **8**，不能为 0 | 最多返回多少条检索条目；同命名空间合并后外层对象数可能更少 |
| 相似度阈值／rerank | 此链没有额外阈值或二次排序器 | 无共享词的文档不进候选；不是“无论多不相关都补满 8 个” |

依赖源码：[search.rs](https://docs.rs/crate/bm25/2.3.2/source/src/search.rs)、[分词器](https://docs.rs/crate/bm25/2.3.2/source/src/default_tokenizer.rs)、[词频权重和默认参数](https://docs.rs/crate/bm25/2.3.2/source/src/embedder.rs)、[倒排索引与打分](https://docs.rs/crate/bm25/2.3.2/source/src/scorer.rs)。Codex 默认数量：[tool_discovery.rs:7](https://github.com/openai/codex/blob/e72da2b53805894878023d01949a25a082e0a5cb/codex-rs/tools/src/tool_discovery.rs#L7)。

**注意依赖中的 `Embedder` 命名：它把词哈希成 ID、保存稀疏词频权重，不是调用神经网络生成语义向量。** 没有 Embedding 模型名、维度、HNSW、`efSearch` 或 `nprobe`。英文关键词和分词配置会影响匹配，不保证中文问法与英文工具描述自动语义对齐。

## 3. 检索结果怎样进入后续 LLM call

[search:246](https://github.com/openai/codex/blob/e72da2b53805894878023d01949a25a082e0a5cb/codex-rs/core/src/tools/handlers/tool_search.rs#L246) 将文档 ID 映射回声明；[normalize_search_spec:76](https://github.com/openai/codex/blob/e72da2b53805894878023d01949a25a082e0a5cb/codex-rs/tools/src/tool_search.rs#L76) 将选中函数放入 namespace，并标记 `defer_loading: true`。

[ToolSearchOutput.to_response_item:241](https://github.com/openai/codex/blob/e72da2b53805894878023d01949a25a082e0a5cb/codex-rs/core/src/tools/context.rs#L241) 生成如下结构；业务工具内容为教学示意：

```json
{
  "type": "tool_search_output",
  "call_id": "search_call_1",
  "status": "completed",
  "execution": "client",
  "tools": [{
    "type": "namespace",
    "name": "functions",
    "description": "Functions available to call",
    "tools": [{
      "type": "function",
      "name": "get_order",
      "description": "查询订单状态",
      "parameters": {
        "type": "object",
        "properties": {"order_id": {"type": "string"}},
        "required": ["order_id"]
      },
      "defer_loading": true
    }]
  }]
}
```

```text
模型产生 tool_search_call
→ 本地 BM25 搜索
→ 完整定义进入正式 tool_search_output
→ 输出记录到对话历史
→ 下一轮 Prompt.input 携带该历史输入项
→ Responses API 识别并加载声明
→ 模型产生业务函数调用 → 原注册表负责执行
```

输出入历史：[stream_events_utils.rs:417](https://github.com/openai/codex/blob/e72da2b53805894878023d01949a25a082e0a5cb/codex-rs/core/src/stream_events_utils.rs#L417)；下一轮历史输入：[turn.rs:514](https://github.com/openai/codex/blob/e72da2b53805894878023d01949a25a082e0a5cb/codex-rs/core/src/session/turn.rs#L514)；[build_prompt:1563](https://github.com/openai/codex/blob/e72da2b53805894878023d01949a25a082e0a5cb/codex-rs/core/src/session/turn.rs#L1563)。

**这不是普通 `function_call_output.output` 字符串，也不是只返回工具 ID。** 定义在 Responses 的 **`input` 数组**中，以专用输入项传入；该接口不是 Chat Completions 的 `messages` 数组。支持这条协议时无需仅为搜索命中而把所有命中工具改成顶层直接工具。源码可证明传输结构，服务端最终 token 渲染及缓存收益未实测。[官方客户端工具搜索说明](https://developers.openai.com/api/docs/guides/tools-tool-search)


# Claude Code：ToolSearch 内部实现与定义加载

**结论：本次 CC 源码镜像使用关键词加权检索，不是向量检索，也不是 Anthropic API 的服务端 BM25 搜索工具。命中后返回 `tool_reference`，下一轮请求补上对应的延迟工具声明，由 API 展开引用。**

- 核验日期：2026-10-16；仅静态阅读，未运行 CC 或测量缓存。
- 源码：[第三方学习镜像](https://github.com/wuwangzhang1216/claude-code-source-all-in-one)，Commit `68eaad61694df7a752cbe348d7d69a652953abd7`，`package.json` 标为 `2.1.152`。
- **证据边界：镜像包含提取源码及维护者后续修改，不是 Anthropic 官方发布的完整源码，不能把其算法、版本号当作当前官方二进制的逐字证明。** 官方产品文档只用于交叉核对工具搜索与延迟加载行为。

## 1. search tool 内部做什么

入口：[ToolSearchTool.ts:21](https://github.com/wuwangzhang1216/claude-code-source-all-in-one/blob/68eaad61694df7a752cbe348d7d69a652953abd7/src/tools/ToolSearchTool/ToolSearchTool.ts#L21)、[call:326](https://github.com/wuwangzhang1216/claude-code-source-all-in-one/blob/68eaad61694df7a752cbe348d7d69a652953abd7/src/tools/ToolSearchTool/ToolSearchTool.ts#L326)。

```json
{"query":"+slack send message","max_results":5}
```

1. 从宿主已有的 `tools` 中筛出延迟工具；`alwaysLoad` 工具不进延迟集合，MCP 工具和 `shouldDefer` 工具按规则进入。
2. `select:A,B` 直接按名称选择、去重；查不到时也检查全部工具，已加载工具再次选中可直接返回。
3. 普通查询先检查完整名称是否精确匹配，再处理 `mcp__服务名` 前缀，最后进入关键词评分。
4. 无匹配时返回空集合；如果 MCP 服务仍在连接，附上其名称供模型稍后再搜。这个版本没有在搜索函数内自动等待连接。

内部返回值示意（工具名和数量为假设）：

```json
{
  "data": {
    "matches": ["mcp__slack__send_message"],
    "query": "+slack send message",
    "total_deferred_tools": 200
  }
}
```

这里的 key 就是工具名称；不返回向量、相似度或完整 Schema。

## 2. 关键检索：查哪里、怎么打分、有什么参数

实现：[searchToolsWithKeywords:186](https://github.com/wuwangzhang1216/claude-code-source-all-in-one/blob/68eaad61694df7a752cbe348d7d69a652953abd7/src/tools/ToolSearchTool/ToolSearchTool.ts#L186)。

**没有向量入库。** 搜索时遍历内存中的候选工具；名称拆词，描述由 `tool.prompt(...)` 取得，并按工具名 memoize（缓存计算结果）。延迟工具名称集合变化时清空描述缓存；不是数据库索引。

- 名称解析：`mcp__slack__send_message` → `slack / send / message`；普通工具按 CamelCase、下划线拆分。
- 查询：转小写、按空白拆词；`+slack` 表示该词必须匹配名称、描述或 `searchHint`，再对剩余候选评分。
- 描述与 `searchHint` 使用转义后的 `\b词\b` 正则匹配词边界；不是语义相似度，不会自动理解任意同义词。

每个查询词的加分规则：

| 匹配位置 | MCP 工具 | 普通工具 |
|---|---:|---:|
| 名称词片段完全相同 | +12 | +10 |
| 名称词片段包含查询词 | +6 | +5 |
| 完整规范化名称包含查询词，且累计分数仍为 0 | +3 | +3 |
| `searchHint` 命中词边界 | +4 | +4 |
| 描述命中词边界 | +2 | +2 |

教学推演：名称 `mcp__slack__send_message` 对三个词各获 12 分；若描述也包含三个完整词，再加 6 分，共 42 分，`searchHint` 可继续加分。不是实际运行成绩。

最终仅保留 `score > 0`，降序排序、取 `max_results` 个，默认 **5**。权重写死在实现中，不是用户配置；`select:` 分支不经过这次排名截断。

原始源码短摘录，仅补中文注释；上游已算出每个候选的分数：

```ts
return scored
  .filter(item => item.score > 0) // 去掉所有查询词都没有命中的工具。
  .sort((a, b) => b.score - a.score)
  .slice(0, maxResults) // 截取候选，而非执行业务工具。
  .map(item => item.name)
```

| 关注项 | 本实现实际情况 |
|---|---|
| 入库字段 | 无入库；名称、`tool.prompt()` 描述、`searchHint` 在内存中匹配 |
| Embedding 模型、维度、距离函数 | 均不适用 |
| 分块、向量索引、`efSearch` / `nprobe` | 均不适用 |
| 查询参数 | `query`、`max_results=5`；查询支持 `select:`、`+必含词` |
| 阈值 | 仅过滤零分，没有语义相似度阈值 |
| 描述缓存边界 | 按工具名缓存，名称集合不变但描述改变时，此处不会仅因描述变化自动失效 |

## 3. 搜索结果怎样进入后续 LLM call

结果映射器 [ToolSearchTool.ts:444](https://github.com/wuwangzhang1216/claude-code-source-all-in-one/blob/68eaad61694df7a752cbe348d7d69a652953abd7/src/tools/ToolSearchTool/ToolSearchTool.ts#L444) 生成下面的**正式协议块**，不是包含接口说明的普通文本：

```json
{
  "type": "tool_result",
  "tool_use_id": "toolu_search_1",
  "content": [
    {"type":"tool_reference","tool_name":"mcp__slack__send_message"}
  ]
}
```

它位于 `messages` 中 `role: "user"` 的工具结果消息里，紧接对应的 assistant 工具调用。

```text
ToolSearch 返回引用 → 工具结果进入 messages
→ extractDiscoveredToolNames 扫描消息中的 tool_reference
→ filteredTools 保留非延迟工具 + 已发现的延迟工具
→ toolToAPISchema 生成 name / description / input_schema / defer_loading
→ 下一轮请求同时提交 messages 和 tools
→ Anthropic API 把引用展开成模型可识别的完整工具定义
→ 模型生成实际业务工具调用 → Harness 执行
```

关键连接点：

- [提取已发现名称：toolSearch.ts:562](https://github.com/wuwangzhang1216/claude-code-source-all-in-one/blob/68eaad61694df7a752cbe348d7d69a652953abd7/src/utils/toolSearch.ts#L562)。压缩边界另保存此前已发现集合。
- [筛选下一轮工具：claude.ts:1213](https://github.com/wuwangzhang1216/claude-code-source-all-in-one/blob/68eaad61694df7a752cbe348d7d69a652953abd7/src/services/api/claude.ts#L1213)；[构造声明：1290](https://github.com/wuwangzhang1216/claude-code-source-all-in-one/blob/68eaad61694df7a752cbe348d7d69a652953abd7/src/services/api/claude.ts#L1290)。
- [Schema 转换：api.ts:119](https://github.com/wuwangzhang1216/claude-code-source-all-in-one/blob/68eaad61694df7a752cbe348d7d69a652953abd7/src/utils/api.ts#L119)；[实际请求 tools：claude.ts:1770](https://github.com/wuwangzhang1216/claude-code-source-all-in-one/blob/68eaad61694df7a752cbe348d7d69a652953abd7/src/services/api/claude.ts#L1770)。

**缓存重点：这个镜像会在请求 `tools` 中增加命中的延迟声明，但 API 将延迟声明排除在初始提示前缀之外、在引用处展开。因此不能仅凭“tools 数组变化”断言前缀一定变化；缓存命中尚未实测。** 这条链使用 `tool_reference`，没有以 `tool_addition → tool_definition` 发送完整定义。

官方交叉核对：[CC MCP 工具搜索](https://code.claude.com/docs/en/mcp#scale-with-mcp-tool-search)、[自定义搜索结果的 tool_reference 格式](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool#custom-tool-search-implementation)。服务端 Regex/BM25 是 API 提供的另两种实现，不能据此把本镜像的本地关键词函数写成 BM25。


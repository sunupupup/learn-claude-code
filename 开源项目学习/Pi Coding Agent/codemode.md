# 工具的懒加载

| 方式 | 查到的工具说明放在哪里？ | 模型接下来调用谁？ |
|---|---|---|
| 按需加载，直接 tool call | 加入请求的 `tools` 数组 | 直接调用具体工具 |
| Code Mode 查询工具 | 作为 `codemode` 的返回消息，进入对话上下文 | 再调用 `codemode`，由脚本调用具体工具 |


按理来说，一般是 tool_search 找出需要的tool，然后放到 tools 数组中，给到 LLM 进行后续的 tool call
```
tools: [工具搜索入口, 新加载的工具定义]
messages: [对话历史, 搜索结果]
```

但是 codemode 不同

```
tools: [codemode]
messages: [对话历史, codemode 返回的工具说明]
```


codemode 本身是一个大一统的工具， 在工具说明里面有 searchTools、describeTool、tools.call 等能力
每次工具的调用，都是一次js脚本的执行

比如一个链路：文档搜索工具，需要调用三次 codexmode

1. 找文档相关的工具。

```js
tools.codemode(text = "await searchTools('搜索文档');")
```
假如得到的是 search_docs 这个工具

2. 查看这个工具怎么传参数

```js
tools.codemode(text = "await describeTool('search_docs')")
```

3. 调用真正查询文档工具

```js
tools.codemode(text = "await tools.search_docs({ query: 'OpenSandbox 如何接入 MCP' })")
```


# 设计里面：不希望太多的tool，污染上下文
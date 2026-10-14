# Onyx：工具管理与 MCP 接入

## 学习问题与范围

- 对应截图：EP08；进度：已初始化，源码入口已初步定位。
- 当前问题：企业动作怎样变成模型可用工具，并由 Runtime 调用外部系统？
- 本次只做模块介绍与入口分析，后续逐个小问题深入。

## 简单介绍与我的理解

Tool（工具）包含描述、参数与执行实现；MCP（Model Context Protocol，模型上下文协议）用于连接外部工具和资源。模型产生结构化调用意图，真正的操作由运行时及外部服务执行。

**我的理解（学习概括）：**需要分清“注册了什么”“本轮模型可见什么”“用谁的身份执行”。Onyx 连接外部 MCP 是客户端方向；Onyx 把企业搜索提供给其他 Agent 是服务端方向，两者都存在，不能混为一谈。

## 源码位置与阅读方向

- [Tool 接口](https://github.com/onyx-dot-app/onyx/blob/32c08fb95c3b829570466258958bbc8b3f129ad7/backend/onyx/tools/interface.py#L16)（`backend/onyx/tools/interface.py`）：查看工具定义与执行契约。
- [construct_tools](https://github.com/onyx-dot-app/onyx/blob/32c08fb95c3b829570466258958bbc8b3f129ad7/backend/onyx/tools/tool_constructor.py#L156)（`backend/onyx/tools/tool_constructor.py`）：观察本轮工具集合怎样构建；可见范围与注册库存分开看。
- [_safe_run_single_tool / run_tool_calls](https://github.com/onyx-dot-app/onyx/blob/32c08fb95c3b829570466258958bbc8b3f129ad7/backend/onyx/tools/tool_runner.py#L118)（`backend/onyx/tools/tool_runner.py`）：实际分派工具执行并收集结果，包含并行执行路径。
- [MCPTool.run](https://github.com/onyx-dot-app/onyx/blob/32c08fb95c3b829570466258958bbc8b3f129ad7/backend/onyx/tools/tool_implementations/mcp/mcp_tool.py#L147)（`backend/onyx/tools/tool_implementations/mcp/mcp_tool.py`）：外部 MCP 工具调用与凭据、请求头、OAuth 处理。
- [search_indexed_documents](https://github.com/onyx-dot-app/onyx/blob/32c08fb95c3b829570466258958bbc8b3f129ad7/backend/onyx/mcp_server/tools/search.py#L276)（`backend/onyx/mcp_server/tools/search.py`）：反方向：向外部 MCP 客户端提供 Onyx 知识搜索。

阅读方向：工具装配 → 模型收到工具定义 → ToolCallKickoff → run_tool_calls → 具体 Tool.run → ToolResponse → Agent Loop。

- 下一小步：先追一个 SearchTool，再对照一个 MCPTool，确认执行身份和错误怎样传回模型。

## 源码与证据

- 固定 Commit：`32c08fb95c3b829570466258958bbc8b3f129ad7`；读取日期：2026-10-15。
- 本地源码：`D:\code\third-party-labs\agent\source-reading\onyx`；位于学习仓库外。
- 证据状态：所列文件和符号已静态核验；完整模块调用链、部署与运行效果待验证。
- 边界与待验证：MCP 协议本身不保证业务授权、幂等或回滚；当前未确认所有外部写操作都有统一人工审批，不把“安全执行”当已验证事实。
- [项目入口与版本、许可证说明](README.md)。

## 问题验收

1. 从工具装配到模型提出调用，再到 Tool.run 返回结果，分别由谁负责？为什么“注册了工具”“模型能看到工具”和“用户有权执行工具”要分别核查？
2. Onyx 调用外部 MCP 工具，与外部 Agent 通过 MCP 查询 Onyx，有什么方向和身份上的区别？为什么接入 MCP 本身不能保证业务授权或失败回滚？

## 我的笔记


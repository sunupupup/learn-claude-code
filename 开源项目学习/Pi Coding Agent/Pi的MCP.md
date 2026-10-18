# Pi对于MCP的态度

Pi 现在确实原生支持 MCP，而且官方专门发文解释了为什么改变立场

时间线

| 时间 | 官方态度与变化 |
|---|---|
| **2025-11-30** | Mario 明确表示不支持 MCP，主要批评工具定义占用上下文，并推荐按需读取说明的 CLI 工具。[作者原文](https://mariozechner.at/posts/2025-11-30-pi-coding-agent/#no-mcp-support) |
| **2026-09-29** | Codemode 与 MCP 的实现合入主线，提交为 `8562bcf`。[实现与讨论 PR #10040](https://github.com/earendil-works/pi/pull/10040) |
| **2026-09-29** | 团队发布 **《“You Said No MCP!”》**，正面解释态度转变。[官方解释](https://earendil.com/posts/you-said-no-mcp/) |
| **2026-10-01** | Pi 1.0 正式发布，明确列出原生 MCP、Codemode 和延迟工具加载。[官方发布说明](https://earendil.com/posts/pi-1-0/) |


原文：

> 像 Playwright MCP（21 个工具，1.37 万令牌）或 Chrome DevTools MCP（26 个工具，1.8 万令牌）这样的热门 MCP 服务器，会在每次会话中把它们全部的工具描述直接导入你的上下文。这意味着你在开始工作之前，上下文窗口的 7-9%就已经消失了。很多这些工具你在每次游戏中都用不到。

其实他就是讨厌 MCP 的工具描述，占用太多的上下文了

对，按他早期的观点，你这个总结基本准确：他更倾向于让 Agent 通过“本地手册 + CLI”使用能力。

| 形式 | 实际调用链 |
|---|---|
| **直接做成 CLI** | Agent → bash → CLI → 业务 API |
| **把 MCP 包装成 CLI** | Agent → bash → CLI 包装器 → MCP 服务 → 业务 API |

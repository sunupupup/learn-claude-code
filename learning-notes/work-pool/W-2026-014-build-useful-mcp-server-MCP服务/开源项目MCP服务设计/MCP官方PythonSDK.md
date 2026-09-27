# MCP 官方 Python SDK

## 项目资料

- 仓库：[modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk)
- 文档：[Python SDK](https://py.sdk.modelcontextprotocol.io/)、[协议版本](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/protocol-versions.md)、[Server](https://github.com/modelcontextprotocol/python-sdk/tree/main/docs)
- 分类：官方协议 SDK，源码公开；实现 MCP Client 与 Server。
- 维护/版本：截至 2026-09-26 官方仓库将 v2 标为当前稳定线，支持 `2026-07-28` 及早期 revision；v1.x 保持安全/关键错误修复。v2 是重大重构，原 v1 教程、导入路径与 API 不应直接套用。
- 许可证：MCP 仓库迁移期，Apache-2.0 新贡献、部分既有 MIT 内容；需在固定版本检查 LICENSE 与包依赖。

## 能回答的问题

如何用 Python 声明工具、资源和 Prompt；Client 怎样建立 stdio/Streamable HTTP 连接；SDK 如何在新版 `server/discover` 和旧版 initialize handshake 间协商；异常和工具错误如何转成协议结果。

## 建议阅读

1. v2 Getting Started 的 real host/server；
2. `MCPServer`、`Client` API 和 Tools/Resources/Prompts 教程；
3. Streamable HTTP 与 stdio transport 实现；
4. `docs/protocol-versions.md` 里的 auto/legacy/version pin 说明；
5. 对应 release notes、conformance tests 和安全配置。

## 前置与难度

需理解 Python 函数、async context manager、类型注解和 HTTP 基本概念。难度中。与仓库 s19 的 Python 示例连续，推荐作为首选 SDK 主项目；先由用户确认目标语言后再进入源码固定与运行。

## 优点、局限与状态

优点是示例语言熟悉、Client 和 Server 都可观察，版本迁移文档清楚。局限是 v2 刚重构、API 与 v1 差异大，不能把 SDK 自动处理协商/认证说成产品间共同保证。官方活跃，release 页和 v2 文档在 2026-09-26 可见近期更新；这只是维护迹象，不是生产成熟度结论。

## Context7

Resolve：`/modelcontextprotocol/python-sdk` 与官方 `py.sdk.modelcontextprotocol.io` 文档。已查询 Server/Client、HTTP transport 和版本协商；并以官方仓库 Release/Protocol Versions 复核 `2026-07-28` 支持和稳定线状态。

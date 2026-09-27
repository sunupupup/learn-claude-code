# MCP 官方规范与 Schema

## 身份与入口

- 规范文档：[官方 MCP Specification](https://modelcontextprotocol.io/specification/2026-07-28)
- 规范、Schema 和版本历史仓库：[modelcontextprotocol/modelcontextprotocol](https://github.com/modelcontextprotocol/modelcontextprotocol)
- 当前阅读入口：[2026-07-28 Changelog](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/changelog.mdx)、[server/discover](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/server/discover.mdx)、[Streamable HTTP](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http)、[2026 Schema](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/schema/2026-07-28/schema.json)。
- 分类：规范/文档/JSON Schema，不是一个可部署的 MCP Server 项目。
- 许可证：MCP 官方仓库在向 Apache-2.0（新代码/规范）和 CC-BY-4.0（一般文档）迁移；既有未获重许可的内容仍可能按 MIT。引用或再分发时核对具体文件。核验日期 2026-09-26。

## 本章重点

以 `2026-07-28` 作为当前核验版：官方 Changelog 说明协议级 Session、Streamable HTTP `Mcp-Session-Id` 以及 `initialize` / `notifications/initialized` 被移除；请求使用 `_meta` 携带协议版本、客户端能力等；`server/discover` 必须由 Server 实现，用来返回支持版本和能力。方法变化还包括：`subscriptions/listen` 取代旧 HTTP GET 事件流和 `resources/subscribe` / `resources/unsubscribe`；多轮请求/响应替代旧会话里的服务端反向请求；`ping`、`logging/setLevel`、`notifications/roots/list_changed` 被移除，Roots、Sampling、Logging 被弃用。list 结果可携带缓存提示，但是否以及如何缓存仍由实现按授权上下文处理。服务器如需跨请求业务状态，应使用明确业务句柄等方式表达。

版本同时调整服务到客户端的交互：用多轮请求/响应表达需要补充输入的场景，用 `subscriptions/listen` 承载双方约定的订阅通知；若读旧版例子，逐条标记哪些旧 method、session 头或方向调用在新版改变。不要把“stateless”简化成无 TCP 连接、无持久化或无业务状态。

## 学习问题与顺序

1. 按“Host — Client — Server — 下游业务”画一条 `tools/call` 成功链。
2. 对照 2025-11-25 与 2026-07-28：初始化、版本选择、能力发现、会话、反向请求、订阅通知和被移除的方法分别变化什么？
3. 按需要学习 `tools/list/call`、`resources/list/read`、`prompts/list/get`，再读 Transport 与 Authorization 章节。
4. 后续实现只引用所选版本的规范与 schema，并用 SDK/客户端契约测试验证。

## 难度和证据边界

初学者可从概览和 changelog 开始；完整 Schema 适合在遇到字段疑问时查阅，直接通读会增加负担。规范定义要求，不证明所有 SDK/产品都遵守；产品支持状态另查官方 release 和实际运行。

## Context7 核验

- Resolve 命中官方库 ID：`/websites/modelcontextprotocol_io_specification_2026-07-28`（另有仓库 `/modelcontextprotocol/modelcontextprotocol`）。
- 已查询当前版本生命周期、Streamable HTTP、`server/discover` 与 stateless 行为；Context7 返回内容与官方仓库 2026-07-28 changelog 相互核对。

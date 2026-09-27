# FastMCP

## 项目资料

- 仓库：[PrefectHQ/fastmcp](https://github.com/PrefectHQ/fastmcp)
- 文档：[FastMCP 4 Documentation](https://gofastmcp.com/)、[Quickstart](https://gofastmcp.com/getting-started/quickstart)、[更新记录](https://gofastmcp.com/updates)
- 分类：Python MCP 开发框架，源码公开，提供 Server/Client 的更高层 API。
- 维护/版本：更新页在 2026-08-31 宣布 FastMCP 4.0.0 稳定，面向新版 Python SDK 与 `2026-07-28`，并支持旧协议客户端协商；9/26 核验仍有 v4 后续更新。
- 许可证：Apache-2.0，见仓库 LICENSE。

## 能回答的问题

如何用装饰器快速声明 Tools/Resources/Prompts；依赖注入、组件组合和认证如何简化服务搭建；框架如何暴露多种传输并隐藏重复协议样板。

## 建议阅读

1. `Getting Started / Quickstart`；
2. Tools、Resources、Prompts 声明 API；
3. `Client` 和 Streamable HTTP 部署；
4. Authentication、dependency injection、mounting / composition；
5. v3→v4 或 v1 SDK FastMCP 迁移说明与实现限制。

## 前置与难度

Python 装饰器和函数注解基础；低到中。先用它快速看“业务 handler 怎样挂到 MCP 能力”，随后对照官方 SDK，避免把框架便利 API 当作协议 method。

## 优点、局限与状态

优点是样例短、适合快速验证数据路径和依赖注入。局限是抽象会遮蔽 JSON-RPC、协议版本、错误映射和生命周期细节；近期 v4 重大版本刚发布，正式选用需固定 API、验证当前客户端兼容。

核验日期 2026-09-26；目前仅官方仓库/文档状态，未读源码或运行，不构成生产证明。

## Context7

Resolve 命中官方维护者文档：`/prefecthq/fastmcp`（还有 gofastmcp 官网文档）。已查询 FastMCP v4 的 Tools/Resources/Prompts 声明、HTTP Server、Client/Auth 和 v4 对 Python SDK v2 / 2026-07-28 的兼容说明；与官方更新记录交叉核对。Context7 的 API 例子仅作资料入口，实操需按确认的 FastMCP tag 再查。

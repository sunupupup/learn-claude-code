# MCP 官方 TypeScript SDK

## 项目资料

- 仓库：[modelcontextprotocol/typescript-sdk](https://github.com/modelcontextprotocol/typescript-sdk)
- 文档：[TypeScript SDK v2](https://ts.sdk.modelcontextprotocol.io/v2/)、[Servers](https://ts.sdk.modelcontextprotocol.io/v2/servers)、[Clients](https://ts.sdk.modelcontextprotocol.io/v2/clients)
- 分类：官方协议 SDK，源码公开；实现 MCP Client 与 Server。
- 维护/版本：截至 2026-09-26，官方 Roadmap 标记 v2.0.0（2026-07-27 发布）为稳定线，支持 `2026-07-28`；v1.x 继续至少六个月安全与缺陷维护。该状态来自官方仓库 Roadmap/Release，不等于每个 adapter 已同等成熟。
- 许可证：新贡献 Apache-2.0，既有代码含 MIT；按文件/依赖核查。参见 [官方许可证说明](https://github.com/modelcontextprotocol/modelcontextprotocol/discussions/1995)。

## 能回答的问题

如何把协议契约映射到 TS Server、Client 与 Transport；如何在 stdio/Streamable HTTP 上注册工具；2026 协议的无握手发现如何在库内实现；哪些 Host/Origin 限制、请求大小上限和流关闭责任由适配层处理。

## 建议阅读

1. v2 快速 Server Tutorial；
2. `@modelcontextprotocol/server` 和 `/client` package README/API；
3. transport adapters 的 Streamable HTTP / stdio 路径；
4. `server/discover`、每请求 `_meta`、多轮请求和订阅相关测试；
5. Changelog、Roadmap、Conformance workflow。

## 前置与难度

需能读 TypeScript async/await、JSON Schema 与 Node HTTP。难度中。不要在同时学习 Python SDK 时双线读完整源码；可以先用 Python 走通概念，再把这一项目当作窄对照。

## 优点、局限与状态

优点是与规范同维护组织、类型/schema 较集中，适合追协议方法如何映射成 handler。局限是 v2 刚进入稳定线、适配器和部署组合仍需单独验证；SDK 的校验不覆盖业务对象权限。官方维护活跃，核验日 2026-09-26。

## Context7

Resolve：`/modelcontextprotocol/typescript-sdk`（v1.x/v2 分支）及官方 v2 docs。已查询官方 Server/Client 文档、Streamable HTTP 配置和版本状态；Context7 的 v2 文档与仓库 Roadmap/Changelog 交叉核对。

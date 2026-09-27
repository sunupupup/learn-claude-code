# Docker MCP Gateway

## 项目资料

- 仓库：[docker/mcp-gateway](https://github.com/docker/mcp-gateway)
- 文档：[README](https://github.com/docker/mcp-gateway#readme)、[Security](https://github.com/docker/mcp-gateway/blob/main/docs/security.md)、[Message Flow](https://github.com/docker/mcp-gateway/blob/main/docs/message-flow.md)、[Releases](https://github.com/docker/mcp-gateway/releases)
- 分类：Server 聚合/容器生命周期和本机治理 CLI，源码开源；可把多个 MCP Server 暴露给一个客户端。
- 维护/版本：官方仓库截至 2026-09-26 有 2026-06-25 v0.43.1 release；9 月的安全文档和 advisory 页面有更新。仓库活跃，但本次未确认是否已发布更高正式版；运行时能力部分依赖 Docker Desktop MCP Toolkit / Docker Desktop 版本。
- 许可证：MIT，仓库 LICENSE 核验。

## 能回答的问题

聚合后如何路由到 Server？profile 怎样筛工具？镜像/catalog 来源如何信任？宿主目录 bind、secret、OAuth、stdio 子进程和远程 URL 在哪层受限？工具名称冲突如何处理？

## 建议阅读

架构与 message flow → profile/tools filter → catalog 管理 → Security 中 Origin/Host、SSRF、文件路径、secret、日志字段规则 → 发布安全公告和修复版本。对照 source 与 Docker Desktop UI 文档，标明托管/闭源 UI 能力边界。

## 前置与难度

Docker 容器、环境变量、HTTP 基础；难度中到高。推荐为本章首个治理/部署比较项目，不需要上来就跑多个远程服务。

## 优点、局限与状态

优点是能沿一条真实项目观察本机子进程、容器隔离、凭据和聚合的关系。局限是安全面大：GitHub advisories 记录过 SSRF、文件读取、工具名 shadowing、未认证代理访问等问题；必须按修复版理解，不能从 README 宣称直接推导安全结论。许可证/维护迹象为公开资料，未做代码审计。

## Context7

Resolve 命中官方文档库 `/docker/mcp-gateway`。已查询当前 `gateway run`、profile、catalog、secret、OAuth 和安全参数；对照维护者 README 与 Security Guide。注意 Context7 摘要和某些旧文档仍可能显示已变更的功能旗标/默认值，实操时优先看固定 release 的 CLI help 与同版文档。

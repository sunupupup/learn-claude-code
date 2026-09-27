# agentgateway

## 项目资料

- 仓库：[agentgateway/agentgateway](https://github.com/agentgateway/agentgateway)
- 文档：[项目文档](https://agentgateway.dev/)、[MCP Authorization Example](https://github.com/agentgateway/agentgateway/tree/main/examples/mcp-authorization)、[Releases](https://github.com/agentgateway/agentgateway/releases)
- 分类：云原生 AI/MCP 代理和治理项目，源码公开；不属于 MCP 官方 SDK。
- 维护/版本：截至 2026-09-26 releases 显示 2026-08-27 发布中加入 MCP `2026-07-28`、OAuth Provider 与策略特性；release 同时声明新协议功能尚未有独立完整指南。属于活跃开发且能力快速变化，适合作进阶对照。
- 许可证：仓库采用 Apache-2.0（固定学习时核对所选版本及子目录许可）。

## 能回答的问题

远程 MCP 流量进入集群后，TLS、JWT/OAuth、RBAC/CEL policy、限流、凭据换取和 OpenTelemetry 应放在哪一跳？如何把入站用户 identity 与访问后端的服务身份区分？MCP `_meta` 怎样参与 trace context 传递？

## 建议阅读

先读 architecture/standalone 与 Kubernetes 模式区别；再看 `examples/mcp-authorization`；选一条身份认证路径追至上游 Server；最后读 release 的 2026 protocol support 与 compatibility caveats、token exchange 说明。

## 前置与难度

需 HTTP、OAuth/JWT、Kubernetes Gateway/Envoy 基础。难度高。先完成简单 Server 和身份概念后再学，只选一条策略做对照，不需部署整套集群。

## 优点、局限与状态

优点是可观察集中入口的身份、策略和可观测性边界，适合远程多用户场景。局限是新协议支持刚加、部分指南尚未完整；云原生代理与 MCP Server 本身责任不同，策略配置仍需目标集群测通。项目自述功能不等于生产证明。Apache-2.0/活跃维护状态在 2026-09-26 核验。

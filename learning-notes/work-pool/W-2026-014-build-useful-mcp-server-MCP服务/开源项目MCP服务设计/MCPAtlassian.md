# MCP Atlassian

## 项目资料

- 仓库：[sooperset/mcp-atlassian](https://github.com/sooperset/mcp-atlassian)
- 文档：[README](https://github.com/sooperset/mcp-atlassian#readme)、[Authentication](https://github.com/sooperset/mcp-atlassian/blob/main/docs/authentication.mdx)、[Tool Reference](https://github.com/sooperset/mcp-atlassian/blob/main/docs/tools-reference.mdx)、[Configuration](https://github.com/sooperset/mcp-atlassian/blob/main/docs/configuration.mdx)
- 分类：社区开发的 Jira / Confluence 业务 MCP Server，源码公开；**不是 Atlassian 官方产品**。
- 维护/版本：Release 页在 2026-02-27 显示更新（工具集、多用户 credential validation cache）；9/26 README 与文档仍可访问，但未核实近期 commit/release 是否持续，应在源码选定时检查维护节奏。
- 许可证：MIT；以固定提交 LICENSE 为准。

## 能回答的问题

当 Server 需适配复杂 SaaS API 时，怎样把 90+ 工具按 toolset 过滤？API token、PAT、用户 OAuth 和 MCP OAuth proxy/DCR 各自在哪一跳生效？多租户凭据缓存何时失效？速率、分页、并发、breaker 和只读模式如何协调？

## 建议阅读

Authentication 与多用户 OAuth；toolset/access control；configuration 中 retry、concurrency、rate、pagination、circuit-breaker 设置；从一个只读 Jira search tool 追到业务 API；再选一个写入接口看对象权限和重试边界。

## 前置与难度

要熟悉 REST、OAuth 基本角色与 Jira/Confluence 数据模型。难度中到高。适合作为 GitHub Server 的对照，但不建议同时深入两者。

## 优点、局限与状态

优点是把远程 OAuth、多用户凭证与业务限流都放在真实适配项目里。局限是配置项多、上游产品和认证策略变化快；README 提供的 feature 不等于我们验证了它。更新日期距核验日约七个月，必须再查最新 release/commit/安全公告；目前维护状态标成 🟡 部分核实。

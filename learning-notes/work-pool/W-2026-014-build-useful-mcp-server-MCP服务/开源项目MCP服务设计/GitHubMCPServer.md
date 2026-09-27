# GitHub MCP Server

## 项目资料

- 仓库：[github/github-mcp-server](https://github.com/github/github-mcp-server)
- 文档：[README](https://github.com/github/github-mcp-server#readme)、[Tools/权限与安装](https://github.com/github/github-mcp-server/tree/main/docs)、[Releases](https://github.com/github/github-mcp-server/releases)
- 分类：GitHub 官方发布的业务 MCP Server，Go 源码开源，连接 GitHub API。
- 维护/版本：官方 release 页截至 2026-09-26 显示 1.12.2 于 9/16 发布；活跃维护迹象明确。固定学习时以不可变 tag/commit 为准。
- 许可证：MIT，LICENSE 文件核验。

## 能回答的问题

一个真实业务 Server 怎样将仓库、Issue、PR、代码检索等领域操作拆成 MCP Tools？凭据怎样提供？只读模式、工具集合和 GitHub API 权限如何交互？工具结果中的 Issue/PR 文本怎样视为不可信数据？

## 建议阅读

README 的工具集和权限表、只读模式与 OAuth/PAT 配置；`cmd/github-mcp-server` CLI 入口；内部 GitHub API client/各领域工具包；HTTP/stdio transport、工具过滤及安全相关测试；release 中的 OAuth scope 变化。

## 前置与难度

建议懂 HTTP API、Bearer token、仓库/Issue/PR 基本概念。难度中。先观察只读调用链，若选择真实服务实践必须使用测试仓库和最小权限 token。

## 优点、局限与状态

优点是官方业务服务、release 活跃、read-only mode 清晰，便于对照“工具声明”和 GitHub token 最终权力。局限是功能面广；不少工具可产生写入，read-only 不能替代 token scope、资源级权限和用户审批。项目自述 lockdown 是尽力过滤，不是授权边界；该判断来自 README，安全效果仍需源码/测试核对。

核验日期 2026-09-26；只核对公开仓库、MIT license、README 与近期 releases，未运行或独立审计。

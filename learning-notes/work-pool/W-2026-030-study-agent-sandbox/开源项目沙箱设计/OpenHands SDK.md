# OpenHands SDK：沙箱学习候选

- 定位：后续应用层：Agent 如何使用远程执行环境。
- 状态：推荐/选题阶段，尚未启动源码学习。
- 核验日期：2026-09-26。
- [官方仓库](https://github.com/OpenHands/software-agent-sdk)；默认分支 main；GitHub 元数据显示未归档，最近推送日期 2026-09-26。
- 仓库声明许可证：MIT；正式进入源码阅读时还需核对选定 Commit 的 LICENSE 及相关组件许可。
- 当前证据：官方 README/架构说明与在线目录检查；未逐函数追踪、未运行、未作生产验证。正式学习用 Commit、版本与本地目录均待选定。
- [返回专题大纲](子项目.md)

## 项目简介

提供 Agent、工具、会话、工作区与 Agent Server。适合从 Agent 调用者视角观察远程执行环境的连接和生命周期；不把旧版 OpenHands Runtime 的类名或旧 PR 当作当前实现。

## 适合回答的学习问题

- Agent 会话如何绑定本地或远程 Workspace？
- 工具在客户端还是 Agent Server 执行？
- 文件与终端调用如何形成事件和结果，连接中断怎样处理？
- 工作区关闭与会话结束是否相同，失败清理由谁负责？

## 推荐观察入口

以下是已经检查的在线目录或文档入口；链接随默认分支变化，正式阅读后替换为固定 Commit 的证据链接。

- [远程服务示例：examples/02_remote_agent_server](https://github.com/OpenHands/software-agent-sdk/tree/main/examples/02_remote_agent_server)
- [Workspace 后端：openhands-workspace/openhands/workspace](https://github.com/OpenHands/software-agent-sdk/tree/main/openhands-workspace/openhands/workspace)
- [Agent Server：openhands-agent-server/openhands/agent_server](https://github.com/OpenHands/software-agent-sdk/tree/main/openhands-agent-server/openhands/agent_server)
- [工具包：openhands-tools](https://github.com/OpenHands/software-agent-sdk/tree/main/openhands-tools)

## 首轮范围

先观察远程 Workspace 与 Agent Server，再追一个 terminal 或 file 请求；只有需要理解模型如何选择工具时才往 Agent Loop 扩展。不泛读整套 UI、自动化平台和多 Agent 系统。

## 边界与待核验事项

Agent Server 可以在远程环境内执行会话，不能预设所有产品都是“模型循环在外、仅工具在内”。工作区抽象也不天然保证隔离，需要看具体后端配置。

## 后续小实验候选

先用固定请求观察远程命令与结果，不依赖付费模型。后续如要完整 Agent 运行，再明确模型与实验范围。


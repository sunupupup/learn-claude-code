# Pi Coding Agent

Pi 是可扩展的 Agent Harness，Coding Agent 是其中用于终端编程的 CLI 与 SDK。
本次重点观察会话如何保存为 JSONL 条目树，以及如何从历史构建模型上下文；详细机制逐步学习。

- 官方仓库：[earendil-works/pi](https://github.com/earendil-works/pi)
- 研究范围：`packages/coding-agent`，包名 `@earendil-works/pi-coding-agent`。
- 阅读版本：包版本 `0.87.1`；Commit `d6af72e1857cfb10b41d8ff8e69f0d72b4cf6d31`，不是当前最新版声明。
- 许可证：固定快照根目录 `LICENSE` 已核验为 MIT。
- 源码位置：`D:\code\third-party-labs\agent\source-reading\pi`，在学习仓库外。
- 旧资料：[上下文压缩入口](../../learning-notes/work-pool/W-2026-024-study-production-reactive-context-compaction/开源项目上下文压缩设计/Pi%20Coding%20Agent.md)、[上下文组织与缓存笔记](../../learning-notes/work-pool/W-2026-032-study-agent-context-organization-and-prompt-cache-Context缓存/开源项目缓存设计/Pi%20Coding%20Agent.md)。旧资料仅作关联来源，版本与证据分别核对。

## 学习模块

- [会话管理](会话管理模块.md)：重启后历史怎样读回来并进入模型上下文？学习中；2026-10-11 开始。
- [上下文压缩策略](上下文压缩策略模块.md)：怎样触发压缩、选择保留范围并生成摘要？学习中；2026-10-12 已静态核验默认策略与切分依据。
- [工具管理](工具管理模块.md)：工具怎样注册、启用、执行并返回结果？学习中；2026-10-12 已静态梳理工具机制地图，后续逐项深入。
- [运行生命周期管理](运行生命周期管理模块.md)：运行怎样启动、停止和收尾？先学中断与取消；2026-10-13 已初始化，独立聊天中逐步学习。

# Pi 和 其他Coding Agent的区别

使用关注点不同

- 用 Cursor / Codex 时：主要思考“怎么把任务描述清楚，利用已有能力完成任务”。
- 用 Pi 时：除了完成任务，还会思考“它现在的运行方式哪里不符合我的需求，能不能改造 Harness，让这类任务以后都更好地完成”。

从使用 Agent 完成一次任务，走向设计 Agent 如何持续完成一类任务。
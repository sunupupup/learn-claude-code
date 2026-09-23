# 个人助手 Agent 开源项目与记忆层级

> 记录日期：2026-09-23。这里只整理官方文档所描述的定位与机制，未进行源码审计或运行验证。

## 项目简介

- **Hermes Agent（Nous Research）**：可自托管的通用 Agent，提供命令行（CLI）、桌面端和多种消息渠道入口；重点能力包括跨会话记忆、工具、自动化与可复用 Skill。
- **OpenClaw**：自托管的多渠道 AI 助手，以 Gateway（网关，负责连接聊天应用与 Agent）作为常驻入口，也支持个人和团队使用；内置记忆检索与后台整理能力。

## 记忆模块的四个观察层

| 层级 | 作用 | Hermes | OpenClaw |
| --- | --- | --- | --- |
| **用户记忆** | 稳定偏好、用户背景和长期事实 | `USER.md` 与 `MEMORY.md`；按 profile（独立配置与状态目录）隔离，启动时载入 | `USER.md` 与 `MEMORY.md`；按 Agent 工作区组织，长期记忆在符合条件的会话中载入 |
| **项目/工作区记忆** | 项目约束、环境与工作进度 | 可由项目上下文文件及工作区资料承载；不要误认为内置长期记忆天然按项目分库** | 可由 Agent 工作区中的上下文文件和 `memory/` 日记承载；工作区由部署配置决定 |
| **对话上下文** | 当前任务正在使用的消息、工具结果和临时状态 | 当前会话上下文；旧会话可通过 `session_search`（跨会话搜索工具）按需查找 | 当前会话上下文；记忆检索和可选会话索引用于补查历史 |
| **Skill 沉淀** | 可复用的“怎么做”流程，而非用户事实或聊天日志 | 按需加载；Agent 可创建或修改，属于程序性记忆 | 按需加载的指令文件；支持 Skill Workshop 管理提案与复核 |

**校准后的心智模型：**用户记忆管“关于这个人”，项目/工作区记忆管“关于当前工作对象”，对话上下文管“眼前这次任务”，Skill 管“以后遇到同类任务怎么做”。这是比较两项目的分析框架，不表示两者都实现了四个同名、独立的存储模块。

记忆重视程度上，两者都把跨会话记忆当作产品能力；OpenClaw 官方文档展示了较完整的检索与后台整理链路。功能复杂不等于召回质量已被证明，质量仍需用实际任务评测。

## 官方资料

- [Hermes：Persistent Memory](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/memory.md)
- [Hermes：Skills System](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills)
- [Hermes：Features Overview](https://hermes-agent.nousresearch.com/docs/user-guide/features/overview)
- [OpenClaw：Memory overview](https://docs.openclaw.ai/concepts/memory)
- [OpenClaw：Builtin memory engine](https://docs.openclaw.ai/concepts/memory-builtin)
- [OpenClaw：Dreaming](https://docs.openclaw.ai/concepts/dreaming)
- [OpenClaw：Skills](https://docs.openclaw.ai/tools/skills)

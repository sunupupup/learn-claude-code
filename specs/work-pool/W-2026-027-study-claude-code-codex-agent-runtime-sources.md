# W-2026-027：Claude Code / Codex Agent Runtime 源码与开源项目对照

- Status: ready
- Area: Agent Runtime Source Study / Multi-Agent / Registry / Lifecycle / Open-Source Comparison
- Difficulty: D2 → D3（从教学代码和 README 对照进入固定版本源码考证）
- Discovered From: s17 对 Teammate 重复利用、Registry 查询、动态上下文和“Claude Code/Codex 是否有源码”的追问
- Owner: personal
- Priority: medium

## Objective

建立一个可复查的源码与官方文档对照入口，重点回答：

- Claude Code 的公开仓库和官方 Agent Teams 文档分别公开了什么；
- Codex 的公开源码如何实现 Agent Registry、状态查询、线程关系和父子结果通知；
- 哪些实现是“模型可见 Tool”，哪些是 Runtime 内部状态或动态上下文；
- 哪些开源项目适合继续研究 Teammate 复用、事件通信、状态持久化和 Durable Execution。

本任务只登记研究入口，不把当前网页内容直接当作永久结论。开始研究时必须重新固定版本/Commit、许可证和官方资料。

## Initial Reconnaissance（2026-09-11，待启动时复核）

### Claude Code

- 官方 GitHub 仓库 `anthropics/claude-code` 当前显示为 Public；
- 仓库 `LICENSE.md` 当前写的是 Anthropic Commercial Terms，而不是 Apache/MIT 等标准开源许可证；
- 当前公开仓库树主要可见插件、脚本、示例和文档入口，本轮没有在公开仓库中核验到 Claude Code CLI/Agent Teams 核心运行时代码；
- 官方 Agent Teams 文档公开描述了共享 task list、self-claim、文件锁、team config、mailbox、idle teammate 和 shutdown 等行为；
- 因此先标记为：**官方文档 + 公开仓库线索；核心 Runtime 源码可用性待确认，不把该仓库直接称为标准开源 Runtime。**

### Codex

- 官方 `openai/codex` 仓库公开，并标注 Apache-2.0；
- `codex-rs/core/src/agent/control.rs` 当前可见 `AgentControl`、`AgentRegistry`、`LiveAgent`、`ListedAgent`、`get_status()`、`subscribe_status()` 和 `list_agents()` 等实现入口；
- `maybe_start_completion_watcher()` 负责等待子 Agent 到达最终状态，并向父线程注入完成通知；
- `multi_agents_v2` 下有 `spawn`、`list_agents`、`send_message`、`wait` 等协作 Tool handler；
- `format_environment_context_subagents()` 展示了 Runtime 把部分 Agent 拓扑信息整理为上下文的路径；
- 因此 Codex 是本主题最适合首先阅读的公开源码样本，但要区分“live status/线程状态”与生产意义上的跨机器 heartbeat。

## Problem Statement

产品名词、README、Issue、公开源码和运行时行为可能不一致。尤其需要避免以下错误：

- 把 Claude Code 官方文档中描述的行为当成已经看到内部实现；
- 把一个 Public GitHub 仓库自动等同于 OSI 开源项目；
- 把 Codex 的进程/线程 Registry 自动等同于跨进程、跨主机的 Durable Registry；
- 把 `list_agents`、上下文注入、消息通知和 heartbeat 混为同一种机制；
- 用 Issue、博客或反编译/泄露材料替代维护者源码和官方文档。

## Stable Mental Model

```text
Official docs / public repo / source / runtime experiment
             ↓
fixed version + commit + license + evidence classification
             ↓
source call chain
             ↓
compare:
  identity | registry | status | context injection
  message  | completion watcher | shutdown | persistence
             ↓
production design lessons
```

证据等级必须分开记录：

```text
source-verified ≠ documented ≠ observed-runtime ≠ production-proven
```

## Recommended Learning Order

1. 先读官方 Claude Code Agent Teams 文档，记录 team config、task list、self-claim、file locking、idle 和 shutdown 的产品语义；
2. 再读 Claude Code 公开仓库的目录、许可证和可见脚本/插件，确认“公开了什么、没有公开什么”；
3. 固定 Codex commit，阅读 `AgentControl`、Registry、`list_agents`、状态订阅、completion watcher 和 `multi_agents_v2` handler；
4. 对照 Codex 的 app-server/thread manager，区分 Thread、Agent、Subagent、Session 和持久化图；
5. 阅读 OpenHands 的 AgentController、State、EventStream、Runtime、Session 和 ConversationManager；
6. 阅读 LangGraph 的 checkpointer、thread、store 和 state history，理解“Agent 可恢复状态”与“Worker 存活”不是一回事；
7. 阅读 AutoGen Core/AgentChat 的事件驱动 Runtime 和 Team 实现，观察 Topic、消息、终止和 reset；
8. 阅读 Temporal 的 Workflow、Activity、Task Queue、Heartbeat、Cancellation 和 Durable Execution，作为 Agent Runtime 下方的可靠执行层对照；
9. 最后写出与 s17 的差异报告，明确哪些是状态投影、哪些是控制面、哪些是持久化和恢复机制。

## Core Questions

- Claude Code 当前公开内容是否足以核验 Teammate Registry 和动态上下文实现？
- Codex 的 `list_agents()` 返回的是哪些 Agent，状态如何从 Thread 得到？
- Codex 的父子完成 watcher 是自动事件注入、Tool 结果，还是两者的组合？
- Agent 拓扑上下文是每轮动态生成，还是只在 spawn/resume 时生成？
- 进程内状态 Registry 与跨 Session/跨机器 Registry 的边界在哪里？
- OpenHands 的 EventStream 如何承担 Agent、Runtime 和 Session 的通信？
- LangGraph 的 `thread_id`、checkpoint 和 store 如何支撑恢复与跨线程状态？
- AutoGen 的 Runtime/Topic 与 Lead-Teammate inbox 有什么本质差异？
- Temporal 的 heartbeat/lease/cancellation 哪些概念可以迁移到 Agent Worker？
- 各项目的许可证、版本、活动状态和实际可运行路径是什么？

## Expected Output

- 一张 Claude Code / Codex / OpenHands / LangGraph / AutoGen / Temporal 的能力与证据等级对照表；
- 一份固定 Commit 的 Codex Agent Registry 调用链；
- 一份 Claude Code“官方文档与公开仓库边界”记录；
- 一张 Tool、动态上下文、事件通知、Registry 和持久化的映射图；
- 一份 Agent status、heartbeat、lease、checkpoint、task state 的术语边界表；
- 一份值得深入阅读的开源项目清单与阅读顺序；
- 一份 s17 教学实现与真实项目的差异报告，并区分 source/document/runtime/production 证据。

## Success Criteria

完成后应能够：

1. 说明 Claude Code “公开仓库”“官方文档”“标准开源 Runtime”三个说法的差异；
2. 在 Codex 源码中定位 Agent Registry、状态读取、状态订阅和父子完成通知；
3. 区分动态上下文注入、模型可调用查询 Tool、事件唤醒和底层心跳；
4. 为每个结论标注 source-verified、documented、observed-runtime 或未确认；
5. 选出最多两个主参考项目，避免同时泛读大量框架；
6. 把源码观察转化为 W-2026-025/W-2026-026 可复用的设计问题，而不是直接复制产品名词。

## Why Deferred

本任务需要固定外部项目版本并进行较深源码阅读，超出 s17 当前的教学主线。现在先登记可靠入口和“不确定项”，后续明确启动时再做版本核验和实验。

## Start Trigger

- 用户明确说“开始 W-2026-027”；
- 或明确说“开始看 Claude Code/Codex Agent 源码”；
- 启动时按 [`specs/README.md`](../README.md) 创建对应 Change，并移除本 Work Pool 文件；
- 启动前重新核验 Commit、许可证、官方文档 URL、源码目录和当前行为。

## Boundaries

- 当前只登记研究任务，不安装外部框架、不运行生产服务；
- 只优先使用官方仓库、官方文档和维护者源码；
- Issue、博客和社区文章只能作为线索，不能单独证明实现事实；
- 不使用泄露、反编译或绕过访问控制得到的源码；
- 不把 Public 仓库、可下载二进制和开放文档混成同一个“开源程度”；
- 不把一个项目的状态名或 Tool 名称直接推广成 Agent 系统通用语义。

## Reference Projects

以下项目先作为阅读入口，不代表已经完成深度评估：

- [OpenAI Codex](https://github.com/openai/codex)：最贴近本主题；看 AgentControl、Registry、状态订阅、父子线程和上下文投影；
- [Anthropic Claude Code](https://github.com/anthropics/claude-code)：看官方仓库边界，并配合 [Agent Teams 官方文档](https://code.claude.com/docs/en/agent-teams) 阅读 task list、self-claim、mailbox、idle 和 shutdown；
- [OpenHands](https://github.com/OpenHands/OpenHands)：看 AgentController、State、EventStream、Runtime 和 Session 如何组合；
- [LangGraph](https://github.com/langchain-ai/langgraph)：看 checkpointer、`thread_id`、store、state history 与恢复；
- [AutoGen](https://github.com/microsoft/autogen)：看 Core 的消息传递、事件驱动 Runtime 和 AgentChat Teams；
- [Temporal](https://github.com/temporalio/temporal) / [Temporal Python SDK](https://github.com/temporalio/sdk-python)：看 Durable Execution、Task Queue、Activity heartbeat、取消和优雅 shutdown；它不是 Agent 框架，而是很好的可靠执行层对照。

## Related

- [`s17 Autonomous Agents`](../../s17_autonomous_agents/README.md)
- [`s17 学习笔记`](../../s17_autonomous_agents/LEARNING_NOTES.md)
- [`W-2026-004：生产级 Subagent Runtime`](./W-2026-004-study-production-subagent-runtime.md)
- [`W-2026-019：持久 Teammate 生命周期、Idle Loop 与唤醒`](./W-2026-019-study-persistent-teammate-lifecycle.md)
- [`W-2026-020：Agent-to-Agent 协作方式与通信拓扑`](./W-2026-020-study-agent-to-agent-collaboration-patterns.md)
- [`W-2026-025：Teammate Registry、存活检测与恢复`](./W-2026-025-study-teammate-registry-and-reuse.md)
- [`W-2026-026：Lead 团队状态观察方式`](./W-2026-026-study-lead-team-state-observation.md)

# W-2026-019：持久 Teammate 生命周期、Idle Loop 与唤醒

- Status: ready
- Area: Agent Team / Runtime Lifecycle / Idle Loop / Inbox Delivery / Shutdown / Reliability
- Difficulty: D2 → D3（从教学版有限轮次进入持久 Agent 的生命周期与恢复边界）
- Discovered From: s15 `code.py` 注释中对“Teammate 自己的 Agent Loop”“教学版最多 10 轮”和真实 CC idle loop 的观察与追问
- Owner: personal
- Priority: high

## Objective

理解持久 Teammate 与一次性 Subagent 在生命周期上的工程差异，重点研究：队友如何从 working 进入 idle、如何被 inbox 消息唤醒、如何处理 shutdown、如何记录存活状态，以及进程崩溃后是否能够恢复。

## Problem Statement

s15 教学版的队友在线程中执行固定的 10 轮循环，遇到非 `tool_use`、异常或轮次耗尽后发送结果并退出。README 对真实 CC 的描述则是：队友完成一轮后进入 idle，等待 inbox 消息，收到新任务后继续工作，直到收到 `shutdown_request`。

这两种模型的差异会影响：

- “完成一轮”与“完成整个生命周期”的区别；
- idle 队友是否仍然占用资源、持有权限和保留上下文；
- 消息到达时如何唤醒，以及消息是否重复或丢失；
- shutdown 与正在执行的模型调用、Tool、副作用如何协调；
- daemon 线程退出、进程崩溃和重启后如何恢复；
- Lead 如何知道队友是 working、idle、failed、terminated 还是状态未知。

## Stable Mental Model

```text
spawned
  → working
  → idle_notification
  → wait for inbox
  → receive task/message
  → working
  → shutdown_request
  → finish current safe boundary
  → shutdown_approved
  → terminated
```

需要分别追踪：

- Agent 生命周期状态；
- 当前模型调用和 Tool 状态；
- Inbox 消息状态；
- 任务和副作用状态；
- Lead 对队友状态的观察证据。

## Recommended Learning Order

1. 对照 s15 的 `for range(10)` 和真实生命周期描述，区分有限轮次、idle 和 terminated；
2. 画出 Teammate 状态机与 Lead/Teammate 消息流；
3. 研究 idle 时的资源、上下文、权限和租约策略；
4. 研究 inbox 唤醒、重复投递、ack、超时和消息过期；
5. 研究 shutdown 在模型生成中、Tool 执行中和副作用已发出时的边界；
6. 注入线程退出、进程崩溃、网络失败和重启，验证恢复与未知状态；
7. 使用固定版本的真实项目源码核验，不把教程 README 的版本相关映射直接当作当前生产事实。

## Core Questions

- idle 是一种 Agent 状态、调度状态，还是两者的组合？
- 队友收到 inbox 后，如何避免同一消息触发两次工作？
- `idle_notification` 代表一轮结束、任务完成，还是暂时没有下一步工作？
- shutdown 是否允许打断模型调用或 Tool？如果不允许，安全边界在哪里？
- daemon 线程退出后，哪些状态已经丢失，哪些状态仍可从磁盘或队列恢复？
- Lead 如何区分队友真正退出、网络断开、进程崩溃和长时间无响应？

## Expected Output

- 一张 Teammate 生命周期状态机；
- 一份 inbox 唤醒、ack、重复和过期策略；
- 一张 shutdown 与模型/Tool/副作用状态的边界矩阵；
- 一个 Fake Agent/Fake Inbox 的确定性恢复实验；
- 一份教学版 s15 与真实项目生命周期实现的差异报告。

## Success Criteria

完成后应能够：

1. 解释为什么固定 10 轮循环不等于持久 Teammate；
2. 准确区分 idle、completed、failed、terminated 和 unknown；
3. 设计安全的消息唤醒和 shutdown 状态转移；
4. 说明线程、进程、队列和 Checkpoint 对恢复能力的影响；
5. 处理模型已取消但 Tool 仍在执行、消息已消费但结果未确认等情况。

## Why Deferred

当前先完成 s15 的基础通信和 Agent Loop 阅读；持久生命周期会同时涉及消息可靠交付、锁、取消、Checkpoint 和副作用恢复，暂不在当前章节主线中展开。

## Start Trigger

- 用户明确说“开始 W-2026-019”；
- 或明确说“开始学 Teammate idle loop / 持久生命周期”；
- 启动时按 [`specs/README.md`](../README.md) 创建对应 Change，并移除本 Work Pool 文件。

## Boundaries

- 当前只登记学习任务，不修改 s15 教学实现；
- 不把真实 CC README 映射直接视为已核验的当前源码事实；
- 不把 idle 通知当作业务任务完成证明；
- 不把线程仍存活当作 Agent 状态、任务状态和副作用状态都健康。

## Non-goals

- 不在本任务中实现通用调度器或分布式 Actor 系统；
- 不重复承担 W-2026-017 的完整 Python 锁课程；
- 不重复承担 W-2026-015 的全部消息注入治理；
- 不默认引入持久 Teammate，先用实验确认其生命周期收益和成本。

## Related

- [`s15 Agent Teams`](../../s15_agent_teams/README.md)
- [`s15 学习笔记`](../../s15_agent_teams/LEARNING_NOTES.md)
- [`W-2026-004：生产级 Subagent Runtime`](./W-2026-004-study-production-subagent-runtime.md)
- [`W-2026-013：Task Completion Verification`](./W-2026-013-study-task-completion-verification.md)
- [`W-2026-015：Agent 消息注入、插队与运行时事件交付`](./W-2026-015-study-agent-message-injection-steering.md)
- [`W-2026-017：Python 锁与 Agent 并发状态治理`](./W-2026-017-study-python-locks-and-agent-concurrency.md)

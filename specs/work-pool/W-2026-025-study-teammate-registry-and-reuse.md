# W-2026-025：可重复利用 Teammate 的 Registry、存活检测与恢复

- Status: ready
- Area: Agent Team / Teammate Reuse / Registry / Heartbeat / TTL / Lease / Recovery
- Difficulty: D2 → D3（从 s17 的进程内 Teammate 进入可观测、可恢复的生产生命周期）
- Discovered From: s17 对 Teammate 跨 Lead turn 驻留、timeout、后续任务和“如何知道队友仍然存活”的追问
- Owner: personal
- Priority: high

## Objective

理解生产系统如何重复利用 Teammate，而不是每个任务都重新创建一次 Agent。重点建立以下边界：

- Teammate 身份是否稳定；
- `working`、`idle`、`stopped`、`failed`、`unknown` 分别代表什么；
- Registry 如何记录状态、当前任务、所属 Session 和最后心跳；
- heartbeat、TTL、probe 和 lease 如何判断“仍可复用”；
- Teammate 失联后，任务如何释放、恢复或重新入队；
- 上下文复用带来的收益，是否值得承担 Token、权限、资源和状态污染成本。

## Problem Statement

s17 当前只有进程内的 `active_teammates: dict[str, bool]`。它可以防止重复 spawn，并在线程退出时删除名字，但不能回答：

- Teammate 是正在工作、空闲等待，还是已经崩溃？
- `idle` 是否仍然可以接收新任务？
- 进程重启后，原来的身份和上下文是否还存在？
- `in_progress` 任务对应的 Teammate 如果失联，谁负责恢复？
- Lead 后续 turn 看到的成员状态是否新鲜、是否有时间戳和可信来源？

如果只保留“名字存在”或“任务已被领取”，生产系统很容易把僵尸 Worker 当成可复用 Worker，或者把仍然存活的 Worker 重复创建，丢失上下文并产生重复副作用。

## Stable Mental Model

```text
Spawn / Resume
      ↓
Registry：identity + state + last_heartbeat + current_task
      ↓
working ↔ idle
      │       │
      │       └─ 可复用，但仍需检查 heartbeat / TTL / 权限 / 资源
      │
      ├─ heartbeat 持续 → alive
      ├─ TTL 过期      → unknown / stale
      └─ shutdown      → stopped

Task lease 过期
      → 任务进入 recovery / requeue
      → 新 Worker 重新 claim
```

Registry 是权威状态来源；动态提示词、UI 状态和 Lead 的自然语言记忆都只是观察投影，不能替代 Runtime 的状态校验。

## Recommended Learning Order

1. 回看 s17 的 `active_teammates`、`idle_poll()`、`timeout` 和 daemon thread；
2. 对照 W-2026-019，区分“生命周期状态”与“存活检测/可复用资格”；
3. 设计最小 Registry schema：身份、状态、Session/Worker ID、当前任务、最后心跳、状态版本；
4. 比较 heartbeat、主动 probe、事件通知和 TTL 的准确性、成本与误判；
5. 研究 Task lease 与 Teammate lease 的关系，覆盖崩溃、网络分区、重复恢复和幂等；
6. 研究上下文复用与重新 spawn 的取舍：延迟、Token、权限、隔离、上下文污染和模型状态；
7. 用确定性 Fake Worker 实验验证 idle → reuse、heartbeat 过期、任务恢复和 graceful shutdown；
8. 固定一个真实项目的版本，记录它的 Registry、状态和恢复证据，不把 README 的状态名直接当作通用标准。

## Core Questions

- `idle` 是“进程仍存活”，还是“可以安全接收新任务”？
- Registry 状态应该只存在内存，还是需要跨进程/跨 Session 持久化？
- heartbeat 多久发送一次，TTL 如何选择，网络抖动时如何避免误杀？
- 主动 probe 能否区分“Agent 忙”与“Agent 死亡”？
- Worker 正在执行 Tool 或副作用时，lease 过期能否安全重试？
- Teammate 的上下文复用是否会泄露上一个任务的权限、假设或未完成状态？
- Lead 重启、Registry 重启和 Teammate 重启分别如何恢复？
- 哪些状态需要由 Registry 强制维护，哪些信息可以只作为 Prompt 上下文？

## Expected Output

- 一张 Teammate 状态机：created、starting、working、idle、stopping、stopped、failed、unknown；
- 一份 Registry 数据契约，包含心跳、TTL、当前任务和状态版本；
- 一张 heartbeat / probe / event / TTL 的方案对照表；
- 一份 Teammate lease 与 Task lease 的恢复协议；
- 一个 Fake Registry/Fake Worker 的确定性实验；
- 一份“复用已有 Teammate vs 新建 Teammate”的生产决策表；
- 一份 s17 教学版与生产级 Registry/恢复机制的差异报告。

## Success Criteria

完成后应能够：

1. 区分 `idle`、`alive`、`reusable`、`unknown` 和 `terminated`；
2. 说明为什么 `active_teammates[name] = True` 不是生产级 liveness 证明；
3. 设计带 TTL 和 lease 的最小 Teammate/Task 恢复流程；
4. 解释上下文复用的性能收益与安全、隔离、污染风险；
5. 用实验说明 Worker 失联后不会自动把旧任务当成已完成；
6. 指出哪些结论来自真实源码，哪些只是设计建议或版本相关文档。

## Why Deferred

当前 s17 的主线是“Teammate 在 IDLE 中主动发现和认领任务”。Registry、heartbeat、lease 和跨进程恢复会同时牵涉 W-2026-017 的并发、W-2026-013 的完成验证、W-2026-019 的生命周期和 W-2026-004 的 Runtime，因此先独立登记，暂不扩展本章代码。

## Start Trigger

- 用户明确说“开始 W-2026-025”；
- 或明确说“开始学习 Teammate Registry / heartbeat / 复用 / 存活检测”；
- 启动时按 [`specs/README.md`](../README.md) 创建对应 Change，并移除本 Work Pool 文件。

## Boundaries

- 当前只登记学习任务，不修改 s17 的 Teammate 生命周期；
- 不把线程、进程、Session、Agent、Task 和 Artifact 的状态混成一个 `status`；
- 不把 heartbeat 当作任务完成证明；
- 不把 TTL 过期直接等同于确定死亡，应保留 `unknown` 或 fencing 语义；
- 不在本任务中实现通用分布式调度器、容器编排或完整消息中间件。

## Non-goals

- 不重复承担 W-2026-019 的全部 idle/shutdown/inbox 课程；
- 不重复承担 W-2026-017 的全部锁与并发课程；
- 不重复承担 W-2026-013 的任务完成验证；
- 不默认选择“永久驻留 Teammate”，先用成本、可靠性和安全证据判断。

## Related

- [`s17 Autonomous Agents`](../../s17_autonomous_agents/README.md)
- [`s17 学习笔记`](../../s17_autonomous_agents/LEARNING_NOTES.md)
- [`W-2026-004：生产级 Subagent Runtime`](./W-2026-004-study-production-subagent-runtime.md)
- [`W-2026-013：Task Completion Verification`](./W-2026-013-study-task-completion-verification.md)
- [`W-2026-017：Python 锁与 Agent 并发状态治理`](./W-2026-017-study-python-locks-and-agent-concurrency.md)
- [`W-2026-019：持久 Teammate 生命周期、Idle Loop 与唤醒`](./W-2026-019-study-persistent-teammate-lifecycle.md)
- [`W-2026-026：Lead 团队状态观察方式`](./W-2026-026-study-lead-team-state-observation.md)
- [`W-2026-027：Claude Code / Codex Agent Runtime 源码对照`](./W-2026-027-study-claude-code-codex-agent-runtime-sources.md)

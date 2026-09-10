# W-2026-026：Lead 感知团队状态：查询 Tool、动态上下文与事件注入

- Status: ready
- Area: Agent Observation / Registry Read Model / Tool Contract / Dynamic Context / Runtime Events
- Difficulty: D2 → D3（从“Lead 能否看到 Teammate”进入控制面与模型上下文的接口设计）
- Discovered From: s17 对 Lead 后续 loop 如何感知 Teammate 存活，以及“查询 Registry 用 Tool 还是 system prompt”的追问
- Owner: personal
- Priority: high

## Objective

比较 Lead 感知 Teammate/Registry 状态的三种入口，并形成可落地的混合方案：

1. Lead 按需调用 `list_teammates` / `get_teammate_status` Tool；
2. Runtime 在每次 Lead LLM 调用前注入动态团队状态摘要；
3. Runtime 通过状态事件、消息或唤醒机制主动把变化送入 Lead。

目标不是简单选择“Tool”或“Prompt”，而是区分：状态的权威来源、模型看到的投影、状态的新鲜度，以及真正执行动作时的再次校验。

## Problem Statement

当前 s17 没有 Lead 可调用的 Registry 查询 Tool。Lead 只能通过任务板、inbox 结果或间接发送消息来推断 Teammate 状态；这会混淆以下问题：

- Teammate 是否还活着；
- Teammate 当前是工作、空闲还是等待外部输入；
- Teammate 是否可以接受新任务；
- Teammate 最近一次状态是什么时候；
- 该状态是实时读取、缓存快照，还是模型历史中的旧信息。

把完整 Registry 每轮塞进 system prompt 会浪费上下文并可能过期；只依赖 Tool 又可能让模型忘记查询、增加一次调用，或在等待期间错过重要事件。因此需要一个明确的观察契约。

## Stable Mental Model

```text
Registry（权威状态）
       │
       ├─ list/get Tool：按需查询，适合细节和动作前确认
       ├─ 动态 Runtime Context：每轮注入摘要，适合稳定提醒
       └─ Event / Wake-up：状态变化时主动通知，适合异步任务

模型看到的是 observation projection
       ↓
真正的 claim / send / shutdown / reassign
       ↓
Runtime 再次读取并校验 Registry，不信任 Prompt 快照
```

动态 system prompt 更准确地说是“Runtime 在本次模型调用前重新组装的上下文”。它不是模型自己修改 system prompt，也不能自动保证状态实时。

## Recommended Learning Order

1. 以 s17 的 Lead 工具和 `active_teammates` 为基线，列出当前缺失的状态查询能力；
2. 设计 `list_teammates`、`get_teammate_status` 和 `ping_teammate` 的最小 Tool Schema；
3. 设计动态上下文摘要：状态、当前任务、`last_seen`、`as_of`、来源和过期标记；
4. 比较每轮注入、事件触发、按需查询和混合策略的 Token、延迟和新鲜度；
5. 研究状态快照被 Prompt Injection、错误消息或旧缓存污染时的边界；
6. 研究 Lead 在新 turn 开始、Tool 前、等待期间和异常恢复时何时刷新状态；
7. 用 Fake Registry 做对照实验：无查询、Tool、动态上下文、事件+Tool；
8. 固定真实项目版本，比较它如何向父 Agent 暴露成员、状态、结果和关闭事件。

## Core Questions

- 什么状态适合每轮动态注入，什么状态必须由 Tool 按需读取？
- 是否需要把 `as_of`、TTL 和 `unknown` 强制放进模型可见的状态摘要？
- Lead 忘记调用查询 Tool 时，Runtime 是否应该自动注入或触发提醒？
- 状态事件是直接进入 Lead history、单独的 control-plane channel，还是唤醒下一轮？
- `list_teammates` 返回的是成员目录、实时 liveness，还是最后已知状态？
- Tool 返回的状态与 Prompt 快照冲突时，谁优先，如何记录冲突？
- 在 shutdown、reassign、claim 等动作前，怎样避免使用过期状态？
- 如何限制 Registry 信息的权限，避免把其他租户、秘密或内部路径暴露给模型？

## Expected Output

- 一张 Tool / 动态上下文 / 事件注入的比较矩阵；
- 一份最小 Registry read model 与 Tool Schema；
- 一份动态状态摘要格式，包含时间、来源、TTL 和 unknown 语义；
- 一张 Lead 生命周期中的刷新时机图；
- 一组状态过期、冲突、事件重复和 Tool 失败的 Eval；
- 一条推荐的混合方案：摘要用于 awareness，Tool 用于 fresh read，Runtime 用于最终 gate。

## Success Criteria

完成后应能够：

1. 解释为什么动态 Prompt 可以改善 awareness，但不能作为权威状态；
2. 判断成员目录、实时 liveness、当前任务和完成证据分别应从哪里读取；
3. 为 Lead 设计“每轮摘要 + 动作前查询/校验”的最小控制面；
4. 处理状态快照过期、事件丢失、Tool 不可用和 Registry 冲突；
5. 用实验比较 Tool、动态上下文和事件注入的成本与可靠性。

## Why Deferred

这个主题是一个小巧但独立的生产知识点。它依赖 W-2026-025 对 Registry/liveness 的定义，但不应在 s17 主线中直接实现；先保存问题、接口和评测边界，后续单独学习。

## Start Trigger

- 用户明确说“开始 W-2026-026”；
- 或明确说“开始学习 Registry 查询 Tool 和动态 system prompt 的取舍”；
- 启动时按 [`specs/README.md`](../README.md) 创建对应 Change，并移除本 Work Pool 文件。

## Boundaries

- 当前只登记学习任务，不修改 Lead Tool Schema 或 system prompt；
- 不把动态上下文当作权限、任务 claim 或 shutdown 的最终控制边界；
- 不重复承担 W-2026-015 的全部消息注入治理，但要引用其注入风险；
- 不假设所有生产系统都需要模型可调用的成员列表 Tool；
- 不把 UI 面板存在、消息发送成功或任务状态当作唯一 liveness 证明。

## Non-goals

- 不在本任务中实现完整 Registry、心跳服务或事件总线；
- 不设计通用 Prompt 管理平台；
- 不把某一个厂商的工具名直接抽象成所有 Agent 系统的标准；
- 不在没有新鲜状态校验的情况下自动触发 shutdown、reassign 或副作用。

## Related

- [`s17 Autonomous Agents`](../../s17_autonomous_agents/README.md)
- [`s17 学习笔记`](../../s17_autonomous_agents/LEARNING_NOTES.md)
- [`W-2026-015：Agent 消息注入、插队与运行时事件交付`](./W-2026-015-study-agent-message-injection-steering.md)
- [`W-2026-019：持久 Teammate 生命周期、Idle Loop 与唤醒`](./W-2026-019-study-persistent-teammate-lifecycle.md)
- [`W-2026-020：Agent-to-Agent 协作方式与通信拓扑`](./W-2026-020-study-agent-to-agent-collaboration-patterns.md)
- [`W-2026-025：Teammate Registry、存活检测与恢复`](./W-2026-025-study-teammate-registry-and-reuse.md)
- [`W-2026-027：Claude Code / Codex Agent Runtime 源码对照`](./W-2026-027-study-claude-code-codex-agent-runtime-sources.md)

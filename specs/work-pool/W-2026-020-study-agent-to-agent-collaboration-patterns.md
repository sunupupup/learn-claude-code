# W-2026-020：Agent-to-Agent 协作方式与通信拓扑

- Status: ready
- Area: Agent Collaboration / Agent-to-Agent Communication / Delegation / Handoff / Inbox / Task Board / Peer Coordination / Eval
- Difficulty: D2 → D3（从协作模式辨析进入生产级协议、权限和评测边界）
- Discovered From: s15 学习过程中对 Subagent、Teammate、跨 Lead Turn 驻留、跨 Session 协作以及 Agent 之间通信方式的重新分类
- Owner: personal
- Priority: high

## Objective

专门研究 Agent 之间如何协作，建立不依赖厂商命名的比较框架。重点区分协作拓扑、生命周期和通信/状态边界，而不是把所有异步线程、后台任务或普通 Workflow 都称为 Agent Team。

目标是能够判断一个问题应该使用：

- 一次性父子委派；
- 持久 Lead-Teammate inbox；
- Handoff（控制权交接）；
- 层级子团队；
- 共享任务板或 Blackboard（黑板式协作）；
- Peer-to-Peer（同级 Agent 点对点协商）；
- 跨进程/跨 Session 的 Durable Agent 协作。

## Problem Statement

不同 Agent 系统可能都使用“Subagent”“Team”“Handoff”“Worker”或“Swarm”等词，但真实协作语义可能完全不同。需要分别回答：

- 谁拥有任务和最终验收责任；
- Agent 是一次性、有限多轮、空闲等待还是可恢复的 Durable 逻辑实体；
- 消息是返回值、定向 inbox、共享任务状态、事件还是控制权交接；
- Agent 是否能主动发现、选择、委派和监督其他 Agent；
- 上下文、权限、Artifact、状态和副作用如何在 Agent 之间传递；
- 失败、取消、重复消息和部分成功如何归责与恢复。

## Stable Mental Model

```text
Agent-to-Agent Collaboration
  = Topology
  × Lifecycle
  × Communication / State Boundary
  × Authority / Verification
```

常见组合：

```text
s06：parent-child × one-shot × direct result
s15：lead-worker × bounded multi-turn × inbox
Handoff：single active owner × control transfer × context handoff
Task Board：many workers × claim-based lifecycle × shared task state
Peer Team：peer topology × message exchange × shared coordination rules
Durable Team：any topology × cross-process/session state × event delivery
```

“跨 Session”主要是持久化和运行边界，不是单独的拓扑；跨 Session 的 Agent 仍可以采用父子、Lead-Worker、Peer 或任务板协作。

## Recommended Learning Order

1. 固定术语：Subagent、Teammate、Handoff、Peer、Worker、Blackboard、Task Board 和 Durable Agent；
2. 以 s06/s15 为基线，比较一次性委派和进程内多轮 inbox 协作；
3. 研究 Handoff 与 Lead-Worker 的责任和控制权差异；
4. 对比直接消息、共享任务板、事件总线和共享 Artifact；
5. 研究层级 Team 与 Peer-to-Peer/Swarm 的授权、冲突和结果汇总；
6. 研究跨进程/跨 Session 协作的身份、Registry、checkpoint、ack、重试和恢复；
7. 选择一个主开源项目和最多一个窄对照，固定版本/Commit，使用 Context7、官方文档和维护者源码核验调用链；
8. 用固定 Eval 比较不同协作方式的成功率、延迟、成本、上下文压力、消息可靠性和副作用风险。

## Core Questions

- 一次性 Subagent 和多轮 Teammate 的最小边界是什么？
- Handoff 是新 Agent 接管同一任务，还是只复制一份上下文？
- 直接 inbox、任务板和事件总线分别适合什么协作关系？
- Peer Agent 没有 Root Lead 时，谁负责冲突解决和最终验收？
- 什么时候层级委派有收益，什么时候只是增加消息和协调成本？
- Durable Teammate 是否需要模型可调用的 `list_teammates`，还是 Runtime 内部 Registry 足够？
- Agent 身份、角色、权限、租户、Run 和 Task ID 如何关联？
- 如何避免重复委派、消息环路、无限嵌套、结果丢失和副作用重复？

## Expected Output

- 一张 Agent-to-Agent 协作方式对照表：拓扑、生命周期、通信、状态、授权和验收；
- 一份 Subagent / Teammate / Handoff / Task Board / Peer / Durable Team 决策矩阵；
- 一张消息、Artifact、Context、权限和最终责任的流转图；
- 一个包含 `list_teammates`、`send_message`、`handoff`、`claim_task` 等能力的最小控制面契约草案；
- 一组覆盖消息重复、成员崩溃、权限升级、层级环路和部分成功的 Eval；
- 至少一个真实开源项目的固定版本协作调用链，以及与 s15 教学实现的差异报告。

## Success Criteria

完成后应能够：

1. 只用拓扑、生命周期和通信边界解释不同 Agent 协作模式；
2. 判断任务应使用一次性委派、持久队友、Handoff、任务板、Peer 或层级 Team；
3. 解释为什么 Durable Team 需要 Registry，但不必然需要模型可调用的成员列表 Tool；
4. 为一种协作模式写出消息、权限、失败和验收契约；
5. 用真实项目代码和 Eval 证据支持协作方式选择，而不是只依据产品名词。

## Why Deferred

当前继续 s15 的基础通信和生命周期学习，不立即展开完整 Agent 协作模式调研。该任务会横跨 s06、s15、s16、s17 以及生产 Runtime、权限、评测和恢复问题，适合作为独立 Work Pool。

## Start Trigger

- 用户明确说“开始 W-2026-020”；
- 或明确说“开始研究 Agent 之间的协作方式”；
- 启动时按 [`specs/README.md`](../README.md) 创建对应 Change，并移除本 Work Pool 文件；
- 进入真实项目调研前，重新核验版本、Commit、许可证、活动状态和当前官方资料。

## Boundaries

- 当前只登记学习任务，不安装外部框架、不运行生产项目、不修改 s15 行为逻辑；
- 主要研究 Agent-to-Agent 协作，不把普通 Background Task 或确定性 Workflow 当作 Agent 协作模式；
- 不假设“跨 Session”天然意味着 Peer-to-Peer；
- 不把 Agent 数量、层级深度或消息数量本身当作质量证明；
- 不把模型生成的自然语言结果当作最终完成验证。

## Non-goals

- 不构建通用 Agent 通信协议或消息中间件；
- 不重复承担 W-2026-004 的全部 Subagent Runtime 调研；
- 不重复承担 W-2026-015 的全部运行时消息注入治理；
- 不默认实现多层 Team，只有评测证明协作收益超过协调成本时才考虑。

## Related

- [`s06 Subagent`](../../s06_subagent/README.md)
- [`s15 Agent Teams`](../../s15_agent_teams/README.md)
- [`s15 学习笔记`](../../s15_agent_teams/LEARNING_NOTES.md)
- [`W-2026-004：生产级 Subagent Runtime`](./W-2026-004-study-production-subagent-runtime.md)
- [`W-2026-015：Agent 消息注入、插队与运行时事件交付`](./W-2026-015-study-agent-message-injection-steering.md)
- [`W-2026-018：Agent Team 层级设计与委派拓扑权衡`](./W-2026-018-study-agent-team-hierarchy-and-delegation.md)
- [`W-2026-019：持久 Teammate 生命周期、Idle Loop 与唤醒`](./W-2026-019-study-persistent-teammate-lifecycle.md)

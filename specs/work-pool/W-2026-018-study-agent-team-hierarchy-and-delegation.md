# W-2026-018：Agent Team 层级设计与委派拓扑权衡

- Status: ready
- Area: Agent Team / Hierarchical Delegation / Subagent / Runtime / Governance / Eval
- Difficulty: D2 → D3（从角色和拓扑辨析进入生产级委派边界与故障治理）
- Discovered From: s15 Agent Teams 学习中对 Lead、Teammate、一次性 Subagent 和持久嵌套子团队的讨论
- Owner: personal
- Priority: high

## Objective

研究 Agent Team 的设计层级和委派权衡，建立能够应用到生产系统与开源项目的判断框架：什么时候使用扁平的 Lead + Teammates，什么时候允许一个 Teammate 成为局部子团队 Lead，什么时候只允许一次性 Subagent，什么时候应该拒绝继续拆分。

核心理解起点是：

> Lead 与 Teammate 首先是协作角色和拓扑位置，而不是完全不同的 Agent 类型；一个 Teammate 理论上可以在自己的领域内承担局部 Lead 角色。

本任务要进一步验证这个直觉的工程代价，而不是默认“层级越多越强”。

## Problem Statement

s15 展示的是一个 Lead 加多个 Teammate 的扁平结构。用户已经识别出一种可扩展拓扑：

```text
Root Lead
  └─ Domain Lead / Teammate
       └─ One-shot Subagents 或局部 Teammates
```

但不同拓扑会改变：

- 任务分配和结果汇总路径；
- 上下文、消息和 Artifact 的边界；
- 权限继承与继续委派的授权；
- Token、延迟、模型调用和工具预算；
- 失败、取消、shutdown 和重试的传播；
- Trace、Eval、审计和最终责任归属。

需要明确比较三种选择：

1. 扁平 Team：Root Lead 直接管理所有 Teammates；
2. 层级 Team：Domain Lead 管理自己的子团队；
3. 受限嵌套：非 Lead 默认只能创建边界清晰的一次性 Subagent。

## Stable Mental Model

```text
User Goal
   ↓
Root Lead：拆分领域、授权和验收
   ├─ Persistent Teammate：独立执行域
   │    ├─ One-shot Subagent：短任务、单次结果
   │    └─ Optional Domain Subteam：只有获得明确授权才创建
   └─ Persistent Teammate
        ↓
Result Contract → Domain Validation → Root Integration → Final Verification
```

角色和生命周期需要分开：

- Lead 是某一层的协调角色；
- Teammate 是团队中的协作节点；
- Subagent 是一种委派执行单元；
- 同一个 Agent 可以在父团队中是 Teammate，在子团队中是 Lead；
- 是否允许这种角色转换，由 Runtime 策略、权限和预算决定。

## Recommended Learning Order

1. **固定术语**：区分 Agent 类型、角色、生命周期、拓扑、Subagent、Teammate、Workflow Step 和 Background Task。
2. **回看 s15**：标出当前教学实现只支持的扁平结构，以及 `spawn_teammate`、MessageBus、inbox 和结果汇报边界。
3. **比较拓扑**：画出扁平、两层层级和受限一次性委派的调用链、状态和消息路径。
4. **研究授权**：分析谁可以创建子 Agent、能继承哪些工具/凭证/权限、如何防止无限嵌套和权限扩大。
5. **研究运行时**：比较每层的 Context、Compaction、Checkpoint、Inbox、Shutdown、Retry 和 Trace 需求。
6. **建立评测**：用固定任务集比较单 Agent、扁平 Team、层级 Team 和一次性 Subagent 的质量、成本、延迟和失败归责。
7. **真实项目对照**：选择一个主开源项目，最多一个窄对照；启动时固定版本/Commit，使用 Context7、官方文档和维护者源码核验，不根据产品术语相似就认定语义相同。

## Core Questions

- “Lead”是 Agent 类型、权限级别，还是当前拓扑位置？不同系统是否有不同答案？
- 什么任务需要持久子团队，而不是一个一次性 Subagent？
- 非 Lead 创建一次性 Subagent 时，结果应该直接回给它，还是同时登记给 Root Lead？
- 子团队的任务、Inbox、Artifact、Context 和权限如何与父团队隔离或共享？
- 最大嵌套深度和扇出数量由谁决定：模型、Root Lead、Runtime 策略还是业务风险等级？
- 子团队失败时，谁负责重试、取消、降级或向用户升级？
- 如何避免层级带来的重复总结、上下文膨胀、消息环路和预算失控？
- 哪些真实生产或开源系统明确禁止 Teammate 继续创建 Teammate？为什么？

## Expected Output

- 一张 Agent 类型、协作角色、生命周期和拓扑位置的对照表；
- 一份扁平 Team、两层 Team、一次性 Subagent 的决策矩阵；
- 一个受限嵌套委派契约：深度、扇出、预算、权限、结果格式和验收责任；
- 一张父团队/子团队的消息、Artifact、Context、权限和 Trace 边界图；
- 一组覆盖无限嵌套、重复委派、子团队失败、权限升级和结果丢失的 Eval；
- 至少一个真实开源项目的固定版本调用链，以及与 s15 教学实现的差异报告。

## Success Criteria

完成后应能够：

1. 解释为什么 Agent Team 的 Lead/Teammate 首先是角色和拓扑，而不是固定 Agent 类型；
2. 判断一个任务应使用扁平 Team、层级 Team、一次性 Subagent 还是普通 Workflow；
3. 给出限制嵌套深度和扇出的工程理由，而不是只说“太复杂”；
4. 设计非 Lead 受限委派时的权限、预算、生命周期和结果契约；
5. 说明父子团队之间如何处理 Context、消息、Artifact、失败和最终验收；
6. 用真实项目源码和 Eval 证据，而不是名词或演示，支持一个拓扑选择。

## Why Deferred

当前继续 s15 的基础通信和生命周期学习，不立即研究生产级层级编排。该主题会同时涉及 Subagent Runtime、消息注入、权限、上下文、评测和故障归责，适合作为独立 Work Pool 任务。

## Start Trigger

- 用户明确说“开始 W-2026-018”；
- 或明确说“开始 Agent Team 层级/嵌套委派 Work Pool”；
- 启动时按 [`specs/README.md`](../README.md) 创建对应 Change，并移除本 Work Pool 文件；
- 启动真实项目调研前，重新核验版本、Commit、许可证、活动状态和当前官方资料。

## Boundaries

- 当前只登记学习任务，不安装外部框架、不运行生产项目、不修改 s15 教学逻辑；
- 不假设所有系统都允许 Teammate 创建 Teammate；先区分架构可行性和具体产品策略；
- 不把多 Agent 数量或嵌套层级本身当作质量证明；
- 不把模型自然语言中的“我已完成”当作子团队完成证据；
- 不把 Context 隔离误认为权限、文件系统或业务副作用隔离。

## Non-goals

- 不在本任务中实现通用多 Agent 平台；
- 不重复承担 W-2026-004 的全部 Subagent Runtime 调研；
- 不重复承担 W-2026-015 的全部消息注入和 Steering 治理；
- 不默认构建多层持久团队，只有评测证明其收益超过协调成本时才考虑。

## Related

- [`s15 Agent Teams`](../../s15_agent_teams/README.md)
- [`s15 学习笔记`](../../s15_agent_teams/LEARNING_NOTES.md)
- [`W-2026-004：生产级 Subagent Runtime`](./W-2026-004-study-production-subagent-runtime.md)
- [`W-2026-006：Tool Result 压缩、恢复与副作用安全`](./W-2026-006-study-tool-result-compaction-and-recovery.md)
- [`W-2026-013：Task Completion Verification`](./W-2026-013-study-task-completion-verification.md)
- [`W-2026-015：Agent 消息注入、插队与运行时事件交付`](./W-2026-015-study-agent-message-injection-steering.md)
- [`W-2026-017：Python 锁与 Agent 并发状态治理`](./W-2026-017-study-python-locks-and-agent-concurrency.md)

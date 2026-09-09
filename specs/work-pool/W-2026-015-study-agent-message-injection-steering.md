# W-2026-015：Agent 消息注入、插队与运行时事件交付学习

- Status: ready
- Area: Agent Harness / Runtime / Context Engineering / Message Injection / Steering / Reliability / Security / Eval
- Difficulty: D2 → D3（从单 Agent 的非抢占式消息注入进入可恢复、多来源和多用户事件调度）
- Discovered From: `s14_cron_scheduler` 学习过程中对 Cron 消息、后台通知和“消息插队”共同机制的讨论
- Owner: personal
- Priority: medium
- Related:
  - [s08 Context Compact](../../s08_context_compact/README.md)
  - [s10 System Prompt](../../s10_system_prompt/README.md)
  - [s11 Error Recovery](../../s11_error_recovery/README.md)
  - [s13 Background Tasks](../../s13_background_tasks/README.md)
  - [s14 Cron Scheduler](../../s14_cron_scheduler/README.md)
  - [W-2026-004：生产级 Subagent Runtime](./W-2026-004-study-production-subagent-runtime.md)
  - [W-2026-006：Tool Result 压缩、恢复与副作用安全](./W-2026-006-study-tool-result-compaction-and-recovery.md)
  - [W-2026-007：副作用 Tool 的分层安全](./W-2026-007-study-side-effect-tool-security.md)
  - [W-2026-011：System Prompt 与上下文治理](./W-2026-011-study-system-prompt-production-context-governance.md)
  - [W-2026-012：Reactive Context Compaction](./W-2026-012-study-production-reactive-context-compaction.md)
  - [W-2026-013：Task Completion Verification](./W-2026-013-study-task-completion-verification.md)

## Assumptions

1. 本任务当前只进入 Work Pool，不立即修改 `s13`、`s14` 或其他章节代码，也不安装外部框架。
2. “消息注入”是本任务使用的工程描述，不预设它是所有厂商和框架共同采用的标准术语；启动研究时要核对各项目的正式对象名和版本。
3. 当前先研究非抢占式注入：不修改正在进行的模型请求，而是在安全的模型调用边界交付事件；取消、抢占和恢复作为后续进阶。
4. 消息使用 `role: user` 不等于它来自真人用户。来源、身份、权限、优先级和可信度必须由结构化元数据表达，不能只靠自然语言标签。
5. 本任务研究 Agent Harness / Runtime 和 Context Engineering，不研究 LLM 模型内部如何训练或修改注意力机制。

## Objective

建立一套可验证的 Agent 消息注入心智模型：用户输入、Cron 到期、后台任务完成、Tool Result、Runtime 提醒、人工审批和 Agent 间消息等事件，如何经过接收、排队、排序、去重、上下文装配和安全边界，成为下一次模型调用能够消费的消息。

学习目标不是掌握一次 `messages.append()`，而是能够回答：

- 谁产生了这条事件，它是否代表真实用户意图？
- Runtime 在什么状态下允许立即交付、延后、合并、拒绝或取消当前工作？
- 消息应该使用 `user`、`tool_result`、系统指令还是独立事件类型？
- 怎样保持 Tool Call / Tool Result、Run、Task、审批和副作用状态的一致关联？
- 进程崩溃、重复投递、消息乱序和上下文压缩后，如何证明事件没有丢失或重复执行？
- 模型看到的标签、Runtime 的调度策略和业务授权分别负责什么？

## Problem Statement

当前教程已经展示了多种“外部事件进入 Agent 上下文”的简化形式：

```text
s13 后台完成
  → collect_background_results()
  → <task_notification>
  → user-side content

s14 Cron 到期
  → cron_scheduler_loop()
  → cron_queue
  → queue_processor_loop()
  → agent_loop()
  → [Scheduled] prompt 作为 user message
```

这些实现足以展示机制，但还没有形成统一的生产级事件模型：

- 来源和信任主要编码在 `[Scheduled]`、`<task_notification>` 等文本标签中；
- 教学版没有统一的 `event_id`、`source`、`priority`、`created_at`、`run_id`、`correlation_id` 和授权快照；
- `cron_queue` 是由锁保护的进程内列表，没有持久化、确认、重投、优先级和背压；
- s13 的后台通知只能在 Agent Loop 再次经过收集点时被看见；
- s14 的 Queue Processor 只等待 `agent_lock`，没有实现真正的优先级插队；
- 当前代码没有明确表示“已接收、已排队、已注入、模型已观察、动作已执行”这些不同状态；
- 消息注入、Prompt Injection、安全指令、Tool Result 和真人用户消息容易因为都进入 `messages` 而被误认为同一种语义。

## Stable Mental Model

```text
Event Producer
  human / cron / background worker / tool / teammate / runtime / approval
        ↓
Ingress Validation
  schema / identity / authorization / tenant / size / trust
        ↓
Event Queue or Inbox
  priority / ordering / dedupe / persistence / backpressure
        ↓
Delivery Policy
  deliver now / wait / coalesce / reject / cancel-and-restart
        ↓
Safe Injection Boundary
  before model call / after complete tool-result batch / next turn / resume point
        ↓
Context Adapter
  user message / tool_result / system instruction / typed runtime event
        ↓
Context Assembly
  ordering / token budget / provenance / policy / history
        ↓
LLM Call → Agent Action → Tool / Response
        ↓
Ack, State Transition, Trace and User-visible Result
```

核心原则：**标签说明消息是什么，Runtime 决定消息何时进入上下文，授权层决定消息允许驱动什么动作。**

## Terminology And Boundaries

### Message Injection（消息注入）

本任务中的含义是：Harness 在一次模型调用前，把运行时事件转换成模型可消费的消息并加入上下文。它是 Context Engineering 和 Agent Runtime 的交叉机制，不是修改模型权重或模型内部状态。

### Message Steering（消息引导 / 运行中改向）

新的用户要求或系统事件改变当前任务后续方向。Steering 可以采用“等待下一边界”或“取消当前模型请求后重启”等策略，不等同于一定抢占正在执行的 Tool。

### Interruption / Preemption（中断 / 抢占）

Runtime 停止或暂停当前工作，让更高优先级事件先执行。必须分别处理模型请求、Agent Run、Tool 执行和业务副作用；取消模型调用不代表外部 Tool 已取消。

### Prompt Injection（提示注入攻击）

恶意或非可信内容诱导模型越过原有指令和权限。它与 Harness 主动进行的 Message Injection 不是同一个概念，但消息注入管线必须防止把低信任内容升级为高信任命令。

### Context Assembly（上下文装配）

在模型调用前选择、排序、裁剪并隔离 System Prompt、历史、Tool 定义、Tool Result、运行状态和新事件。消息注入只是 Context Assembly 的一个输入来源。

## Learning Tracks

### Track A：事件来源、消息角色与信任边界

- 盘点真人输入、Cron、后台任务、Tool、Subagent、Runtime、审批系统和外部 Webhook 等来源；
- 区分 API 的 `role`、真实事件来源、权限主体和内容可信度；
- 设计统一事件信封：`event_id`、`type`、`source`、`actor`、`tenant_id`、`run_id`、`correlation_id`、`priority`、`created_at`、`payload_ref`、`trust_level`；
- 研究哪些事件可以变成普通 `user` message，哪些必须保留 Tool 或系统协议类型；
- 验证自然语言标签只能帮助模型理解，不能替代身份、授权和调度策略。

### Track B：Agent Loop 状态与安全注入点

- 区分模型调用前、模型流式生成中、Tool Call 已产生、Tool 执行中、Tool Result 批次完成、Turn 结束和等待人工等状态；
- 研究非抢占式注入、取消模型后重启、暂停 Run 后恢复三种策略；
- 保证 `tool_use → tool_result` 协议配对不被高优先级消息破坏；
- 处理一次响应包含多个 Tool Call、部分 Tool 返回、Tool 超时和异步完成；
- 明确“下一次循环迭代”“下一次模型调用”“下一次 Agent Turn”和“新 Run”不是同一个边界。

### Track C：优先级、插队、公平性与背压

- 比较 FIFO、优先级队列、按来源分队列和基于状态机的调度；
- 定义 `urgent / next / normal / later` 等级的语义和允许使用者；
- 研究高优先级消息是否可以取消当前模型调用、是否必须等待 Tool 安全点；
- 处理低优先级消息饥饿、连续用户 Steering、Cron 风暴和通知合并；
- 定义队列长度、单用户配额、丢弃、降级、合并和人工接管策略。

### Track D：消息协议与 Context Engineering

- 对比真人消息、Tool Result、后台通知、定时消息、系统提醒和 Agent 间消息的数据结构；
- 研究注入顺序如何影响模型理解、Tool 选择和未完成计划；
- 处理 Context 超限时哪些消息不可裁剪、哪些可以摘要或外置；
- 为摘要或压缩后的事件保留来源、原始 Artifact 引用和关联 ID；
- 区分“模型已经看到事件”和“Runtime 已把事件写入历史”。

### Track E：可靠交付、并发与恢复

- 设计 `received → queued → selected → injected → observed → acted_on → acknowledged` 状态；
- 比较 at-most-once、at-least-once 和业务幂等实现，避免宣称无法证明的 exactly-once；
- 研究重复消息、乱序、消息过期、进程崩溃、网络重连和 Checkpoint 恢复；
- 处理消息已经注入但模型响应丢失、Tool 成功但事件未确认等未知状态；
- 为副作用动作使用业务幂等键、操作 ID 和状态查询，不以“消息只注入一次”作为安全保证。

### Track F：安全、权限与多租户隔离

- 防止把 Tool 输出、网页内容、邮件或 Subagent 文本误当成真人指令；
- 验证事件来源身份、租户、会话和 Run 归属；
- 对高风险 Tool 在注入后重新鉴权，不继承过期权限快照；
- 研究恶意高优先级事件造成的 Prompt Injection、成本放大和拒绝服务；
- 定义敏感消息的保留、脱敏、删除和审计边界。

### Track G：Observability 与 Eval

- Trace 记录生产、入队、选择、注入、模型观察、动作和确认时间；
- 记录优先级决策、等待原因、取消原因、Context 位置、Prompt/Policy 版本和 Tool 关联；
- 使用确定性测试验证顺序、去重、协议结构和状态迁移；
- 用 Trajectory Eval 检查模型是否正确处理 `[Scheduled]`、通知、用户改向和权限拒绝；
- 监控丢失率、重复率、乱序率、排队时延、注入到响应时延、饥饿时间、取消成本和错误副作用次数。

### Track H：前端与人机协同

- 区分“新消息已收到”“等待安全点”“当前请求已取消”“Tool 仍在执行”和“改向已生效”；
- 显示异步事件来源，避免把系统生成消息伪装成用户刚刚输入；
- 提供编辑、撤回、取消、重试、忽略和人工接管；
- 对冲突消息说明最终采用顺序和未执行事项；
- 设计断线重连后用户能够看到的消息与真实 Runtime 状态。

## Recommended Learning Order

### Phase 1：用当前教程建立统一调用链

1. 从 `s13` 追踪后台 Tool 的占位 `tool_result` 与完成通知；
2. 从 `s14` 追踪 `CronJob → cron_queue → queue_processor_loop → [Scheduled] message`；
3. 对照 `s10` 的 Prompt Assembly 和 `s08` 的 Context Compact，标出消息进入与可能被裁剪的位置；
4. 后续学完 `s15-s16` 后，把 Agent 间 Inbox、请求响应关联和生命周期事件加入同一张图。

### Phase 2：先做无 LLM 的确定性队列实验

用 Fake Agent Loop 和 Fake Tool 构造最小事件管线，先验证：

- 普通消息和高优先级消息的顺序；
- Tool Call / Tool Result 批次期间不能非法插入；
- Agent 空闲时自动唤醒，繁忙时等待；
- 重复 `event_id` 去重；
- 队列满时的背压与明确失败。

先证明 Runtime 行为，再接入真实模型，避免把队列错误误判成模型问题。

### Phase 3：接入模型并观察轨迹

- 用只读或无副作用 Tool 验证定时消息、后台通知和用户 Steering；
- 比较文本标签与结构化来源元数据对模型行为的影响；
- 观察多个消息合并为一次模型调用时，模型是否遗漏或错误排序任务；
- 冻结小型 Eval Set，记录 Prompt、模型、Tool Schema 和事件策略版本。

### Phase 4：加入取消、崩溃和副作用故障

- 模型生成中收到高优先级用户消息；
- Tool 执行中用户要求取消；
- 事件入队后、注入前和注入后分别模拟进程崩溃；
- Tool 已成功但响应丢失时重启恢复；
- 同一事件重复投递、跨租户投递和权限在排队期间被撤销。

### Phase 5：固定版本做真实项目对照

启动时使用 Context7、官方文档和维护者源码，选择一个具有消息队列、Steering 或 Human-in-the-loop 的 Agent Runtime 作为主样本，最多再选一个对照。每个样本固定版本或 Commit，并沿相同链路记录：

```text
event ingress
  → queue
  → priority/arbitration
  → safe boundary
  → context adapter
  → model call
  → tool/action
  → ack/checkpoint
```

不根据产品演示或术语相似就认定两个系统具有相同的中断、恢复和安全语义。

## Minimal Experiments

1. Agent 空闲时注入一条 Cron 消息，验证它启动新 Turn；
2. Tool Result 完成后、下一次模型调用前注入用户 Steering，验证协议仍合法；
3. 一次 assistant 响应包含两个 Tool Call 时注入高优先级事件，验证不能拆坏结果批次；
4. 模型流式输出期间收到用户消息，比较“等待”与“取消后重启”；
5. Tool 执行期间取消模型请求，验证 Tool 状态被独立跟踪；
6. 同一 `event_id` 投递两次，验证模型只处理一次或业务副作用保持幂等；
7. 高优先级消息持续到达，验证普通消息不会永久饥饿；
8. 队列持久化前后模拟崩溃，验证丢失、重复和恢复行为；
9. 注入伪造的 `[Scheduled]` 或 `<task_notification>` 文本，验证文本标签不能获得额外权限；
10. Context 压缩后验证事件来源、关联 ID 和未完成动作仍可恢复。

## Expected Output

- 一张“事件来源 → 队列 → 安全边界 → Context → LLM → Tool”的完整时序图；
- 一份统一事件信封与注入状态机数据契约；
- 一张消息类型、API role、真实来源、信任等级和权限主体的对照表；
- 一份优先级、抢占、取消、合并、过期和背压策略矩阵；
- 一个不依赖真实 LLM 的确定性消息队列实验；
- 一组覆盖顺序、重复、崩溃、协议配对、权限和饥饿的自动化测试；
- 一份 Trace 字段表和故障排查流程；
- 一个真实 Agent Runtime 的固定版本调用链，以及与教程实现的差异报告；
- 一份面向用户的 Steering、取消、等待和恢复交互方案。

## Success Criteria

完成后应能够：

1. 准确区分 Message Injection、Prompt Injection、Context Assembly、Steering、Interruption 和 Tool Result；
2. 解释消息使用 `role: user` 为什么不代表它来自真人用户；
3. 写出非抢占式注入与取消后重启两种状态机，并说明各自安全边界；
4. 设计不会破坏 Tool Call / Tool Result 配对的插队算法；
5. 用确定性测试证明消息顺序、去重、背压和恢复行为；
6. 处理模型已取消但 Tool 仍在运行、Tool 已成功但结果未知等状态；
7. 为事件建立来源、身份、权限、租户、优先级、关联 ID 和审计证据；
8. 用 Eval 和 Trace 区分模型理解失败、Context 装配错误、队列错误和 Runtime 恢复错误；
9. 从真实项目代码指出消息的接收、排队、仲裁、注入、确认和恢复位置；
10. 明确哪些规则必须由 Runtime 和业务授权强制执行，不能交给 Prompt 或模型自觉。

## Reason Deferred

当前 `s14` 只需要掌握 Cron 如何通过进程内队列和 Queue Processor 变成下一次 Agent 输入。完整消息注入会同时涉及 Tool 协议、Context Assembly、优先级、取消、Checkpoint、副作用幂等、多租户、安全、Eval 和 UI，立即展开会打断当前章节的小步学习节奏。

## Start Trigger

- 用户明确说“开始 W-2026-015”或“开始消息注入 Work Pool”等同表达；
- 建议先完成 `s14` 基础验收，至少能够独立解释 Scheduler、Queue、Queue Processor 和 Agent Loop；
- 启动时按 [`specs/README.md`](../README.md) 创建对应的 `specs/changes/C-YYYY-NNN-*.md`，并移除本 Work Pool 文件；
- 进入真实框架对照前，重新核验官方文档、版本、Commit、许可证和可运行条件。

## Boundaries

- 当前只登记学习任务，不自动开始实验或修改教学代码；
- 不把文本标签当成调度优先级、身份凭证或授权；
- 不在 Tool Call / Tool Result 协议未闭合时机械插入不兼容消息；
- 不假设取消模型请求可以取消已经发出的业务副作用；
- 不用内存队列的 Demo 结果证明持久化、跨进程或分布式可靠性；
- 不把“模型收到消息”当成“业务任务已经执行或完成”；
- 不保存完整敏感消息作为默认 Trace，只记录必要元数据和受控引用。

## Non-goals

- 不在本任务中修改模型权重、进行后训练或研究 Transformer 内部机制；
- 不构建通用消息中间件或完整分布式 Agent 平台；
- 不重复承担 `W-2026-011` 的全部 System Prompt 治理内容；
- 不重复承担 `W-2026-012` 的全部 Context 压缩算法；
- 不重复承担 `W-2026-013` 的全部完成验证器设计；
- 不默认引入多 Agent；只有消息来源和协调需求确实需要时才研究跨 Agent 交付。

## Open Questions

- “消息注入”是否应成为统一领域术语，还是按具体系统使用 Event Delivery、Steering、Interrupt、Inbox 或 Pending Notification？
- 哪些事件可以等待下一个模型调用，哪些事件必须取消当前 Run 或交给人？
- 多个来源同时发送消息时，优先级由用户、产品策略、Runtime 还是业务风险决定？
- 一条事件何时算完成：写入队列、加入 Context、模型观察、产生动作，还是业务结果验证通过？
- Context 压缩、模型重试和 Checkpoint 恢复后，怎样保持事件只产生一次可观察业务效果？
- 需要怎样的 UI 才能让用户理解“消息已收到但尚未生效”“模型已改向但 Tool 仍在执行”？

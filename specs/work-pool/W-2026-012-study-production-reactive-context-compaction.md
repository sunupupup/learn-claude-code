# W-2026-012：生产级 Reactive Context Compaction 学习

- Status: ready
- Area: Context Engineering / Error Recovery / Durable Execution / Tool Calling / Eval
- Difficulty: D2 → D3
- Discovered From: `s11_error_recovery` 学习过程；用户发现教学版 `reactive_compact()` 直接保留最后五条消息可能破坏 Tool 配对，并明确提出调研生产级项目的紧急压缩实现
- Owner: personal
- Priority: high
- Related:
  - [s08 Context Compact](../../s08_context_compact/README.md)
  - [s08 学习笔记](../../s08_context_compact/LEARNING_NOTES.md)
  - [s08 压缩方式对比](../../s08_context_compact/压缩方式对比.md)
  - [s11 Error Recovery](../../s11_error_recovery/README.md)
  - [s11 学习笔记](../../s11_error_recovery/LEARNING_NOTES.md)
  - [W-2026-006：Tool Result 压缩、恢复与副作用安全](./W-2026-006-study-tool-result-compaction-and-recovery.md)
  - [W-2026-011：System Prompt 生产级上下文治理、权限与缓存](./W-2026-011-study-system-prompt-production-context-governance.md)

## Objective

研究生产级 Agent 在正常的预估、裁剪和主动压缩仍未避免 `prompt_too_long` 时，如何执行一次可观测、协议有效、状态可恢复且有明确失败边界的紧急上下文压缩，然后安全地重试模型请求。

本任务关注整个活动上下文的应急恢复，不只压缩某一个 Tool Result。目标是从真实项目中提炼可迁移的设计原则，并通过最小实验验证：

```text
检测真实上下文超限
  → 冻结本次 Run 与权限/上下文版本
  → 找到协议安全的压缩切点
  → 保存任务状态、关键事实和副作用凭证
  → 生成或构造紧急摘要
  → 重建合法 messages
  → 在一次性恢复预算内重试
  → 验证结果，或升级为明确失败/人工接管
```

## Problem Statement

`s11_error_recovery/code.py` 的教学实现通过“恢复提示 + 最后五条消息”模拟 reactive compact。它适合展示控制流，但不能直接代表生产方案：

- 按数量截断可能留下孤立的 `tool_result`，或者保留 `tool_use` 却删除对应结果；
- 可能丢失用户目标、已完成步骤、约束、文件引用、计划和待办状态；
- 可能丢失已发生副作用的 `operation_id`、资源 ID、幂等键与审批状态；
- 没有说明上下文已经超限时，摘要模型如何获得可处理的输入；
- 没有 Context Version、Checkpoint、摘要来源和压缩策略版本；
- 压缩后只有一次重试机会，但缺少失败后的降级、人工接管和可恢复契约；
- 最后五条可能仍然超限，也可能因保留内容过少而让任务语义失真。

## Stable Mental Model

Reactive compact 不是一种独立的内容格式，而是一条由真实超限错误触发的应急恢复路径。它可以使用摘要、结构化状态、尾部保留、Artifact 外置或确定性裁剪等手段，但必须满足四个不变量：

1. 消息协议仍然有效，Tool 调用与结果保持配对；
2. 继续任务所需的目标、约束、状态和证据仍然可用；
3. 已发生的业务副作用可核对，不因恢复而重复执行；
4. 恢复过程有版本、预算、Trace 和停止条件。

## Scope Boundary With Related Work

- 本任务研究“整个上下文在超限后的紧急恢复路径”。
- `W-2026-006` 研究“单个或一组 Tool Result 如何压缩、外置、恢复与保证副作用安全”。
- `W-2026-011` 研究更广泛的 Context 来源、租户隔离、权限、注入防护、缓存与版本治理。

三者共享 Tool 配对、版本和恢复问题，但各自保持独立的主要事实来源，避免把所有 Context Engineering 议题合并成一个巨型任务。

## Learning Plan

### Track A：触发、分类与恢复预算

- 区分 proactive compact、阈值触发的 auto compact、手动 compact 和 API 拒绝后的 reactive compact；
- 研究本地 Token 估算与供应商真实计费/限制产生偏差的原因；
- 定义哪些错误可触发紧急压缩，哪些错误应直接终止；
- 设计最多一次或有限次数的恢复预算，并同时限制总耗时、Token、成本和模型调用次数；
- 明确摘要失败、摘要仍超限、重试仍超限时的降级与人工接管路径。

### Track B：协议安全切点与消息重建

- 研究如何识别完整的 `assistant.tool_use → user.tool_result` 组合；
- 处理一次 assistant 消息包含多个 Tool Call、并行结果、部分失败与缺失结果；
- 避免以孤立 `tool_result`、未完成 Tool Call 或非法 role 顺序开始保留尾部；
- 比较“从安全切点保留尾部”“把完整 Tool 交换变成结构化摘要”“保存事件日志后重放 View”三种路径；
- 定义压缩前后的消息协议验证器和确定性断言。

### Track C：摘要、状态与 Artifact 契约

- 区分自然语言摘要、结构化 Run State、业务系统事实和外置 Artifact；
- 设计紧急摘要必须保留的字段：用户目标、已确认约束、当前计划、已完成/未完成步骤、关键文件或来源、错误、预算和下一动作；
- 为副作用 Tool 保留 `operation_id`、`resource_id`、`idempotency_key`、状态与恢复策略；
- 研究当原上下文连摘要模型也无法一次读取时的分块摘要、层级合并或确定性预裁剪；
- 对摘要失真、来源丢失、指令注入和敏感数据扩散建立验证策略。

### Track D：Checkpoint、恢复与并发

- 比较原地修改 messages、生成不可变 Context Snapshot、事件历史 + View 三种状态模型；
- 研究压缩过程中进程崩溃、用户取消、Tool 返回和权限变化产生的竞态；
- 明确恢复后的 Run 使用旧 Context Version 还是重新装配新版本；
- 记录 compact 前后的 Checkpoint、摘要 Hash、策略版本、保留范围和触发错误；
- 验证恢复重放不会重复调用已成功的副作用 Tool。

### Track E：真实项目调用链

启动任务时固定版本、Commit、许可证和文档状态，并从以下候选中选择一个主样本、两个对照样本：

1. **LangChain / LangGraph**：追踪 Summarization Middleware、消息裁剪、Tool 消息安全处理、Checkpoint 和恢复路径；
2. **Pydantic AI**：追踪 message history processor、Tool Call/Return 配对约束和历史处理器的失败行为；
3. **OpenHands Software Agent SDK**：追踪 condenser、事件历史、View、压缩触发与任务状态保留；
4. **Claude Code 教程引用的实现**：在源码可获得且版本可固定时，核对 reactive compact、context collapse、暂存提交和重试状态；无法获得可核验证据时只记录教程主张，不把它当作事实基线；
5. **一个具备 Durable Execution 的 Agent Runtime**：观察 Checkpoint 后压缩、暂停、恢复与重放的版本语义。

每个项目沿同一条调用链记录：

```text
超限检测
  → 触发器
  → 安全切点
  → 摘要/状态生成
  → Tool 配对修复或验证
  → Checkpoint
  → messages 重建
  → 重试与停止
  → Trace / Eval
```

## Research Questions

1. 为什么已经有 proactive/auto compact，生产系统仍需要 reactive compact？
2. 上下文已经超过主模型限制时，系统如何保证压缩器仍能读取必要输入？
3. 哪些事实必须进入摘要，哪些应作为结构化状态或 Artifact 引用保存？
4. 如何证明压缩前后的 Tool Call/Result 仍然完整配对？
5. 如果 Tool 已成功但结果在压缩或崩溃中丢失，恢复时应该查询状态还是重新执行？
6. 摘要模型失败、输出不合法或再次超限时，系统如何 fail closed 或交给用户？
7. Context、Memory、Checkpoint 和业务状态在恢复路径中分别由谁负责？
8. 如何评测任务完成率、事实保留率、协议有效性、恢复成功率、延迟和额外成本？

## Minimal Experiments

1. 构造一个尾部从孤立 `tool_result` 开始的消息列表，证明机械 `messages[-5:]` 无法通过协议验证；
2. 构造一次 assistant 发出两个 Tool Call、只返回一个结果的历史，验证安全切点与错误升级；
3. 比较“只留尾部”“LLM 摘要 + 尾部”“结构化状态 + Artifact 引用 + 尾部”三种方案；
4. 注入摘要调用失败、摘要仍超限、重试仍超限，验证恢复次数和总预算；
5. 模拟 Tool 成功但响应丢失，验证紧急压缩后只查询业务状态，不重复副作用；
6. 在压缩完成、Checkpoint 写入前模拟进程崩溃，验证重启后使用明确版本恢复；
7. 在压缩过程中撤销权限，验证恢复请求不会继续使用过期 Tool 能力。

## Expected Output

- 一张至少三个真实项目的 reactive compaction 调用链对比表；
- 一份 `ReactiveCompactionState` / Context Snapshot 数据契约；
- 一套 Tool 消息配对验证器与安全切点算法；
- 一份紧急摘要字段契约和 Artifact 引用规范；
- 一个使用 fake provider 和可控消息历史的最小实验；
- 至少 8 个确定性测试和 5 个故障注入用例；
- 一张恢复预算表，覆盖次数、截止时间、Token、成本和降级行为；
- 一份 Trace 字段表和“仍无法恢复时”的用户交互方案。

## Success Criteria

完成后应能够：

1. 准确区分 proactive、auto、manual 和 reactive compaction；
2. 从真实项目代码指出超限检测、切点选择、摘要生成、状态持久化和重试的位置；
3. 设计不会产生孤立 Tool 消息的紧急压缩算法；
4. 解释自然语言摘要为什么不能替代业务状态、幂等凭证和 Checkpoint；
5. 用故障注入证明压缩恢复不会重复副作用；
6. 给出摘要失败、再次超限和恢复预算耗尽时的明确终止行为；
7. 用 Eval 数据比较至少三种压缩方案，而不是只观察“请求是否不再报错”。

## Reason Deferred

当前章节先完成 `s11_error_recovery` 的基础错误分类和恢复控制流。生产级 reactive compaction 同时涉及 Tool 协议、Context Engineering、Artifact、Checkpoint、幂等、并发、Eval 和可观测性，现在展开会超过本章的小步学习范围。

## Start Trigger

- 用户明确说“开始 W-2026-012”或同等意思；
- 已完成 `s11_error_recovery` 基础验收；
- 启动时重新核验候选项目的官方文档、版本、Commit 和许可证；
- 按 `specs/README.md` 创建对应的 `specs/changes/C-*.md`，并移除本 Work Pool 文件。

## Boundaries

- 当前只登记后续学习任务，不立即安装框架、下载项目或修改教学代码逻辑；
- 不把“压缩后不再超限”当成成功，必须同时验证任务语义、消息协议和副作用状态；
- 不把 LLM 摘要当作业务事实或唯一 Checkpoint；
- 不在没有幂等或状态核对机制时重放副作用 Tool；
- 不预设某个框架实现就是通用最佳实践，结论必须来自固定版本的代码与实验；
- Trace 默认记录版本、Hash、范围和指标，不默认保存完整敏感上下文。

## Non-goals

- 不在该任务中构建通用 Agent Runtime 或完整分布式工作流平台；
- 不重复研究 `W-2026-006` 已负责的全部 Tool Result 压缩策略；
- 不把 Memory、RAG、System Prompt 和完整聊天历史混成同一种状态；
- 不为了展示复杂度默认引入多 Agent、向量数据库或知识图谱。
